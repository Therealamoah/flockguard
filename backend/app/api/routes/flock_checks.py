from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from google.cloud.firestore import Client, Query

from app.core.deps import get_current_org_id
from app.core.firestore import get_firestore_client
from app.core.refs import flock_checks_ref
from app.models.schemas import FlockCheckCreate, FlockCheckResponse
from app.risk_engine.engine import compute_risk
from app.risk_engine.models import FlockCheckInput, HouseBaseline
from app.services.alert_engine import maybe_create_alert

router = APIRouter(prefix="/farms/{farm_id}/houses/{house_id}/flock-checks", tags=["flock-checks"])

BASELINE_SAMPLE_SIZE = 14


def _load_baseline(db: Client, org_id: str, farm_id: str, house_id: str) -> HouseBaseline:
    """Averages the house's recent Flock Checks into a historical baseline."""
    recent = (
        flock_checks_ref(db, org_id, farm_id, house_id)
        .order_by("recorded_at", direction=Query.DESCENDING)
        .limit(BASELINE_SAMPLE_SIZE)
        .stream()
    )
    records = [doc.to_dict() for doc in recent]
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


@router.post("", response_model=FlockCheckResponse, status_code=201)
def submit_flock_check(
    farm_id: str,
    house_id: str,
    payload: FlockCheckCreate,
    org_id: str = Depends(get_current_org_id),
    db: Client = Depends(get_firestore_client),
):
    """Flock Check -> baseline comparison -> Risk Engine -> Alert Engine."""
    if payload.mortality > payload.bird_count:
        raise HTTPException(status_code=422, detail="mortality cannot exceed bird_count")

    baseline = _load_baseline(db, org_id, farm_id, house_id)

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

    recorded_at = datetime.now(timezone.utc)
    doc_ref = flock_checks_ref(db, org_id, farm_id, house_id).document()
    record = {
        **payload.model_dump(mode="json"),
        "recorded_at": recorded_at.isoformat(),
        "risk_score": risk.score,
        "risk_status": risk.status,
        "risk_factors": [f.model_dump() for f in risk.factors],
    }
    doc_ref.set(record)

    maybe_create_alert(
        db,
        org_id=org_id,
        farm_id=farm_id,
        house_id=house_id,
        flock_check_id=doc_ref.id,
        risk=risk,
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
