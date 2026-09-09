from fastapi import APIRouter, Depends
from google.cloud.firestore import Client, Query

from app.core.deps import get_current_org_id
from app.core.firestore import get_firestore_client
from app.core.refs import flock_checks_ref
from app.services.daily_brief_service import build_daily_brief
from app.services.farm_context_service import get_farm_status, get_flock_history, get_house_comparison, list_houses
from app.services.trend_service import detect_trends

router = APIRouter(prefix="/farms/{farm_id}", tags=["analytics"])

DEFAULT_TREND_DAYS = 30


@router.get("/houses/{house_id}/analytics/trends")
def house_trends(
    farm_id: str,
    house_id: str,
    limit: int = DEFAULT_TREND_DAYS,
    org_id: str = Depends(get_current_org_id),
    db: Client = Depends(get_firestore_client),
):
    """Time series of mortality, feed, water and risk score for one house,
    oldest first, for charting (Recharts) on the House Details / Analytics
    screens."""
    docs = (
        flock_checks_ref(db, org_id, farm_id, house_id)
        .order_by("recorded_at", direction=Query.DESCENDING)
        .limit(limit)
        .stream()
    )
    points = [
        {
            "recorded_at": r.get("recorded_at"),
            "period": r.get("period"),
            "bird_count": r.get("bird_count"),
            "mortality": r.get("mortality"),
            "feed_kg": r.get("feed_kg"),
            "water_level": r.get("water_level"),
            "water_liters": r.get("water_liters"),
            "risk_score": r.get("risk_score"),
            "risk_status": r.get("risk_status"),
        }
        for r in (doc.to_dict() for doc in docs)
    ]
    return list(reversed(points))


@router.get("/analytics/compare-houses")
def compare_houses(
    farm_id: str,
    org_id: str = Depends(get_current_org_id),
    db: Client = Depends(get_firestore_client),
):
    """Latest risk score per house in a farm - powers the AI Health Radar
    and cross-house comparison views. Shared with Ask FlockGuard's farm
    context (app/services/farm_context_service.py::get_house_comparison)
    so the two can never disagree."""
    return get_house_comparison(db, org_id, farm_id)


@router.get("/analytics/trend-insights")
def trend_insights(
    farm_id: str,
    org_id: str = Depends(get_current_org_id),
    db: Client = Depends(get_firestore_client),
):
    """Deterministic, proactive pattern detection across every house in the
    farm (app/services/trend_service.py) - e.g. 3 consecutive checks of
    declining feed. Grok never decides whether a trend exists; Python does.
    """
    insights = []
    for house in list_houses(db, org_id, farm_id):
        history = get_flock_history(db, org_id, farm_id, house["id"], limit=3)
        insights.extend(detect_trends(house["id"], house.get("name") or house["id"], history))
    return insights


@router.get("/daily-brief")
def daily_brief(
    farm_id: str,
    org_id: str = Depends(get_current_org_id),
    db: Client = Depends(get_firestore_client),
):
    """Deterministic daily summary ('3 of 4 houses stable, House C needs
    attention...') built entirely from real data - never itself AI-generated,
    so it works even when Grok is unavailable. See app/api/routes/ask.py's
    POST /ask/daily-brief for an optional, best-effort AI-reworded version.
    """
    status = get_farm_status(db, org_id, farm_id)
    if not status:
        return {"available": False, "reason": "farm_not_found"}
    return {"available": True, **build_daily_brief(status)}
