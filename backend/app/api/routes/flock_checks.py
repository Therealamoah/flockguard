from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from google.cloud.firestore import Client, Query

from app.agent.agent_router import should_investigate_check
from app.agent.event_handlers import investigate_flock_check
from app.core.config import settings
from app.core.deps import get_current_org_id
from app.core.firestore import get_firestore_client
from app.core.limiter import limiter
from app.core.refs import farms_ref, flock_checks_ref, flocks_ref, houses_ref
from app.models.schemas import FlockCheckCreate, FlockCheckResponse, FlockStatus
from app.risk_engine.engine import compute_risk
from app.risk_engine.models import FlockCheckInput, HouseBaseline
from app.services.alert_engine import sync_alert_for_check
from app.services.comparison_service import build_morning_evening_comparison
from app.services.email_service import send_alert_email
from app.services.membership_service import get_notification_emails, get_notification_uids
from app.services.notification_service import alert_email_enabled, push_enabled
from app.services.push_service import send_push_to_uids

# Maps a check's period to the agent trigger name it fires -
# app/agent/agent_router.py decides which skill (if any) responds to each.
_TRIGGER_BY_PERIOD = {
    "morning": "morning_check_submitted",
    "evening": "evening_check_submitted",
    "emergency": "emergency_check_submitted",
}

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


def _get_farm(db: Client, org_id: str, farm_id: str) -> dict:
    """One read used for both the farm's timezone (comparison_service treats
    a missing one as UTC, matching this app's behavior before farm
    timezones existed) and its AI preferences (Settings > FlockGuard
    Intelligence > Proactive Insights) - avoids fetching the farm doc twice."""
    doc = farms_ref(db, org_id).document(farm_id).get()
    return doc.to_dict() if doc.exists else {}


def _proactive_investigation_enabled(farm: dict) -> bool:
    return farm.get("ai_preferences", {}).get("proactive_insights_enabled", True)


async def _notify_new_alert(db: Client, *, org_id: str, farm_id: str, house_id: str, farm: dict, alert: dict) -> None:
    """Runs as a background task (see the add_task call below) so a slow or
    failing send never delays the check-submission response - fires only
    when sync_alert_for_check just OPENED a new alert, not on every later
    check that keeps an already-open one alive, so one ongoing issue
    doesn't turn into a flood of near-duplicate notifications.

    Each channel (Email, Push) is gated independently on the farm's own
    notification preferences (Settings -> Notifications -> Channels): both
    that channel and the alert's own severity toggle
    (critical/warning/watch_alerts) must be on - see
    app/services/notification_service.py, which is the single source of
    truth this and GET /settings both read so they can't disagree about
    what "Email/Push: Available" actually means."""
    house_doc = houses_ref(db, org_id, farm_id).document(house_id).get()
    house_name = house_doc.to_dict().get("name", "A house") if house_doc.exists else "A house"
    farm_name = farm.get("name") or "your farm"

    if alert_email_enabled(farm, alert["status"]):
        to_emails = get_notification_emails(db, org_id)
        if to_emails:
            await send_alert_email(
                to_emails=to_emails,
                farm_name=farm_name,
                house_name=house_name,
                status=alert["status"],
                score=alert["score"],
                factors=[f["label"] for f in alert.get("factors", [])],
            )

    if push_enabled(farm, alert["status"]):
        uids = get_notification_uids(db, org_id)
        if uids:
            send_push_to_uids(
                db,
                org_id=org_id,
                uids=uids,
                title=f"{house_name} needs attention",
                body=f"{farm_name}: risk is now {alert['status'].capitalize()} ({alert['score']} out of 100). Go and check the birds.",
                url=f"{settings.app_public_url}/alerts",
            )


@router.post("", response_model=FlockCheckResponse, status_code=201)
@limiter.limit(settings.rate_limit_flock_check)
def submit_flock_check(
    request: Request,
    background_tasks: BackgroundTasks,
    farm_id: str,
    house_id: str,
    payload: FlockCheckCreate,
    org_id: str = Depends(get_current_org_id),
    db: Client = Depends(get_firestore_client),
):
    """Flock Check -> baseline comparison -> Risk Engine -> Alert Engine.

    Requires an active flock in the house: `bird_count` is no longer
    farmer-entered, it's derived as the flock's current_bird_count minus
    this check's mortality, then persisted back onto both the check and the
    flock doc.

    Also, on this write:
    - stamps `flock_id` on the check, so later queries/comparisons can scope
      by flock, not just house
    - persists `previous_risk_score` / `risk_change` / `previous_check_id`
      so "58 -> 81, +23" never needs a second Firestore scan to display
    - for an evening/emergency check, persists a structured
      `morning_comparison` against that day's Morning Check, if one exists
    """
    if not houses_ref(db, org_id, farm_id).document(house_id).get().exists:
        raise HTTPException(status_code=404, detail="House not found")

    flock_id = _active_flock_id(db, org_id, farm_id, house_id)
    if flock_id is None:
        raise HTTPException(
            status_code=422, detail="Place an active flock in this house before logging a Flock Check"
        )
    flock_ref = flocks_ref(db, org_id, farm_id, house_id).document(flock_id)
    flock_data = flock_ref.get().to_dict() or {}

    recent = _load_recent_checks(db, org_id, farm_id, house_id, RECENT_HISTORY_SAMPLE_SIZE)
    baseline = _load_baseline(recent[:BASELINE_SAMPLE_SIZE])

    # Self-healing fallback for flocks that predate current_bird_count: fall
    # back to the last recorded bird_count, then the placement-day snapshot.
    # No backfill migration needed - the field is (re)persisted below.
    current_count = flock_data.get("current_bird_count")
    if current_count is None:
        current_count = recent[0]["bird_count"] if recent else flock_data.get("initial_bird_count", 0)

    if payload.mortality > current_count:
        raise HTTPException(status_code=422, detail="mortality cannot exceed current bird count")
    new_count = current_count - payload.mortality

    risk_input = FlockCheckInput(
        bird_count=new_count,
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

    farm = _get_farm(db, org_id, farm_id)
    recorded_at = datetime.now(timezone.utc)
    doc_ref = flock_checks_ref(db, org_id, farm_id, house_id).document()

    record = {
        **payload.model_dump(mode="json"),
        "bird_count": new_count,
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
    morning_comparison = build_morning_evening_comparison(
        comparison_candidates,
        {"id": doc_ref.id, **record},
        farm_timezone=farm.get("timezone"),
    )
    record["morning_comparison"] = morning_comparison

    doc_ref.set(record)
    flock_ref.update({"current_bird_count": new_count})

    alert_result = sync_alert_for_check(
        db,
        org_id=org_id,
        farm_id=farm_id,
        house_id=house_id,
        flock_id=flock_id,
        flock_check_id=doc_ref.id,
        risk=risk,
        previous_risk_score=previous_risk_score,
    )

    if alert_result and alert_result["action"] == "created":
        background_tasks.add_task(
            _notify_new_alert,
            db,
            org_id=org_id,
            farm_id=farm_id,
            house_id=house_id,
            farm=farm,
            alert=alert_result["alert"],
        )

    # AI investigation is event-gated (deterministic, no AI call involved in
    # the decision itself - app/agent/agent_router.py) and runs strictly
    # AFTER this response is already on its way back to the farmer, via
    # FastAPI BackgroundTasks - see app/agent/event_handlers.py for why that
    # (and not Celery/Redis/etc.) is the right amount of infrastructure here.
    trigger = _TRIGGER_BY_PERIOD.get(payload.period.value)
    if trigger and _proactive_investigation_enabled(farm) and should_investigate_check(
        risk_status=risk.status,
        risk_change=risk_change,
        has_active_alert=alert_result is not None,
    ):
        background_tasks.add_task(
            investigate_flock_check,
            db,
            org_id=org_id,
            farm_id=farm_id,
            house_id=house_id,
            flock_id=flock_id,
            check_id=doc_ref.id,
            trigger=trigger,
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
        bird_count=new_count,
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
        comparison = build_morning_evening_comparison(
            candidates, check, farm_timezone=_get_farm(db, org_id, farm_id).get("timezone")
        )

    if comparison is None:
        return {"available": False, "reason": "no_morning_check_same_day"}
    return {"available": True, **comparison}
