from fastapi import APIRouter, Depends
from google.cloud.firestore import Client, Query

from app.core.deps import get_current_org_id
from app.core.firestore import get_firestore_client
from app.core.refs import flock_checks_ref, houses_ref

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
    and cross-house comparison views."""
    houses = list(houses_ref(db, org_id, farm_id).stream())

    results = []
    for house_doc in houses:
        latest = (
            flock_checks_ref(db, org_id, farm_id, house_doc.id)
            .order_by("recorded_at", direction=Query.DESCENDING)
            .limit(1)
            .stream()
        )
        latest_check = next((doc.to_dict() for doc in latest), None)
        results.append(
            {
                "house_id": house_doc.id,
                "house_name": house_doc.to_dict().get("name"),
                "risk_score": latest_check.get("risk_score") if latest_check else None,
                "risk_status": latest_check.get("risk_status") if latest_check else None,
                "last_checked_at": latest_check.get("recorded_at") if latest_check else None,
            }
        )

    results.sort(key=lambda r: (r["risk_score"] is None, -(r["risk_score"] or 0)))
    return results
