from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from google.cloud.firestore import Client, Query

from app.core.config import settings
from app.core.deps import get_current_org_id
from app.core.firestore import get_firestore_client
from app.core.limiter import limiter
from app.core.refs import flock_checks_ref, flocks_ref, houses_ref
from app.models.schemas import FlockCheckCreate, FlockCheckResponse, FlockStatus
from app.risk_engine.engine import compute_risk
from app.risk_engine.models import FlockCheckInput, HouseBaseline
from app.services.alert_engine import sync_alert_for_check
from app.services.comparison_service import build_morning_evening_comparison

router = APIRouter(prefix="/farms/{farm_id}/houses/{house_id}/flock-checks", tags=["flock-checks"])

BASELINE_SAMPLE_SIZE = 14
# Enough history to pair same-day Morning/Evening checks and run trend
# detection (trend_service.CONSECUTIVE_WINDOW=3) without an extra query.
RECENT_HISTORY_SAMPLE_SIZE = 14


def _load_recent_checks(db: Client, org_id: str, farm_id: str, house_id: str, limit: int) -> list[dict]:
    docs = (
        flock_checks_ref(db, org_id, farm_id, house_id)
        .order_by("recorded_at", direction=Query.DESCENDING)
        .limit(limit)
        .stream()
    )
    return [{"id": doc.id, **doc.to_dict()} for doc in docs]


def _load_baseline(records: list[dict]) -> HouseBaseline:
    """Averages the house's recent Flock Checks into a historical baseline."""
    if not records:
        return HouseBaseline()

    mortalities = [r["mortality"] for r in records if "mortality" in r]
    feeds = [r["feed_kg"] for r in records if r.get("feed_kg") is not None]
    bird_counts = [r["bird_count"] for r in records if "bird_count" in r]

    return HouseBaseline(
        avg_daily_mortality=sum(mortalities) / len(mortalities) if mortalities else 0.0,
        avg_feed_kg=sum(feeds) / len(feeds) if feeds else None,
        avg_bird_count=round(sum(bird_counts) / len(bird_counts)) if bird_counts else None,
    )


def _active_flock_id(db: Client, org_id: str, farm_id: str, house_id: str) -> str | None:
    docs = flocks_ref(db, org_id, farm_id, house_id).where("status", "==", FlockStatus.ACTIVE.value).limit(1).stream()
    return next((doc.id for doc in docs), None)


@router.post("", response_model=FlockCheckResponse, status_code=201)
@limiter.limit(settings.rate_limit_flock_check)
def submit_flock_check(
    request: Request,
    farm_id: str,
    house_id: str,
    payload: FlockCheckCreate,
    org_id: str = Depends(get_current_org_id),
    db: Client = Depends(get_firestore_client),
):
    """Flock Check -> baseline comparison -> Risk Engine -> Alert Engine.

    Also, on this write:
    - looks up the house's currently active flock (if any) and stamps
      `flock_id` on the check, so later queries/comparisons can scope by
      flock, not just house
    - persists `previous_risk_score` / `risk_change` / `previous_check_id`
      so "58 -> 81, +23" never needs a second Firestore scan to display
    - for an evening/emergency check, persists a structured
      `morning_comparison` against that day's Morning Check, if one exists
    """
    if not houses_ref(db, org_id, farm_id).document(house_id).get().exists:
        raise HTTPException(status_code=404, detail="House not found")
    if payload.mortality > payload.bird_count:
        raise HTTPException(status_code=422, detail="mortality cannot exceed bird_count")

    recent = _load_recent_checks(db, org_id, farm_id, house_id, RECENT_HISTORY_SAMPLE_SIZE)
    baseline = _load_baseline(recent[:BASELINE_SAMPLE_SIZE])

    risk_input = FlockCheckInput(
        bird_count=payload.bird_count,
        mortality=payload.mortality,
        sick_or_injured=payload.sick_or_injured,
        feed_kg=payload.feed_kg,
        water_level=payload.water_level,
        activity=payload.activity,
        feeding_behaviour=payload.feeding_behaviour,
        crowding_observed=payload.crowding_observed,
        unusual_sound_observed=payload.unusual_sound_observed,
    )
    risk = compute_risk(risk_input, baseline)

    previous_check = recent[0] if recent else None
    previous_risk_score = previous_check.get("risk_score") if previous_check else None
    risk_change = risk.score - previous_risk_score if previous_risk_score is not None else None

    flock_id = _active_flock_id(db, org_id, farm_id, house_id)
    recorded_at = datetime.now(timezone.utc)
    doc_ref = flock_checks_ref(db, org_id, farm_id, house_id).document()

    record = {
        **payload.model_dump(mode="json"),
        "house_id": house_id,
        "flock_id": flock_id,
        "recorded_at": recorded_at.isoformat(),
        "risk_score": risk.score,
        "risk_status": risk.status,
        "risk_factors": [f.model_dump() for f in risk.factors],
        "previous_risk_score": previous_risk_score,
        "risk_change": risk_change,
        "previous_check_id": previous_check.get("id") if previous_check else None,
    }

    # Scope comparison candidates to the same flock when the current flock is
    # known, so a freshly placed flock's first Evening Check never pairs
    # against a leftover Morning Check from the house's previous occupant.
    comparison_candidates = [c for c in recent if flock_id is None or c.get("flock_id") in (flock_id, None)]
    morning_comparison = build_morning_evening_comparison(comparison_candidates, {"id": doc_ref.id, **record})
    record["morning_comparison"] = morning_comparison

    doc_ref.set(record)

    sync_alert_for_check(
        db,
        org_id=org_id,
        farm_id=farm_id,
        house_id=house_id,
        flock_id=flock_id,
        flock_check_id=doc_ref.id,
        risk=risk,
        previous_risk_score=previous_risk_score,
    )

    return FlockCheckResponse(
        id=doc_ref.id,
        house_id=house_id,
        period=payload.period,
        recorded_at=recorded_at,
        risk_score=risk.score,
        risk_status=risk.status,
        risk_factors=risk.factors,
        notes=payload.notes,
        previous_risk_score=previous_risk_score,
        risk_change=risk_change,
        morning_comparison=morning_comparison,
    )


@router.get("")
def list_flock_checks(
    farm_id: str,
    house_id: str,
    org_id: str = Depends(get_current_org_id),
    db: Client = Depends(get_firestore_client),
):
    docs = (
        flock_checks_ref(db, org_id, farm_id, house_id)
        .order_by("recorded_at", direction=Query.DESCENDING)
        .stream()
    )
    return [{"id": doc.id, **doc.to_dict()} for doc in docs]


@router.get("/{check_id}")
def get_flock_check(
    farm_id: str,
    house_id: str,
    check_id: str,
    org_id: str = Depends(get_current_org_id),
    db: Client = Depends(get_firestore_client),
):
    doc = flock_checks_ref(db, org_id, farm_id, house_id).document(check_id).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Flock Check not found")
    return {"id": doc.id, **doc.to_dict()}


@router.get("/{check_id}/comparison")
def get_flock_check_comparison(
    farm_id: str,
    house_id: str,
    check_id: str,
    org_id: str = Depends(get_current_org_id),
    db: Client = Depends(get_firestore_client),
):
    """Morning-vs-Evening comparison for one check. Returns the value stored
    at submission time when present; otherwise recomputes it on demand (e.g.
    for checks recorded before this feature existed). `available: false`
    (not an error) when there's no same-day Morning Check to compare against.
    """
    doc = flock_checks_ref(db, org_id, farm_id, house_id).document(check_id).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Flock Check not found")
    check = {"id": doc.id, **doc.to_dict()}

    comparison = check.get("morning_comparison")
    if comparison is None:
        recent = _load_recent_checks(db, org_id, farm_id, house_id, RECENT_HISTORY_SAMPLE_SIZE * 2)
        flock_id = check.get("flock_id")
        candidates = [c for c in recent if flock_id is None or c.get("flock_id") in (flock_id, None)]
        comparison = build_morning_evening_comparison(candidates, check)

    if comparison is None:
        return {"available": False, "reason": "no_morning_check_same_day"}
    return {"available": True, **comparison}
