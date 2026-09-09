"""Structured, tenant-scoped read access to FlockGuard's own data.

Every function here takes `org_id` (derived from the authenticated caller,
never from client input) and returns small, trimmed, JSON-safe dicts meant
to be fed straight into an AI prompt as controlled context - this is the
"tool" layer Ask FlockGuard (app/api/routes/ask.py) uses instead of either
dumping raw Firestore documents or hand-rolling one-off queries per route.

Design rules, followed throughout:
- every read goes through app/core/refs.py, so it's automatically scoped
  under organizations/{org_id}/... - there is no code path here that can
  read another organization's data.
- nothing raises on missing data (no farm/house/flock/history/alerts) -
  callers get None / [] / a small "not found" marker, never a 404/500,
  since "the record isn't available" is a normal, expected answer for an
  assistant to be able to give.
- only the fields worth spending AI context tokens on are returned; full
  documents are never forwarded verbatim.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from google.cloud.firestore import Client, Query

from app.core.refs import alerts_ref, farms_ref, flock_checks_ref, flocks_ref, houses_ref, inspections_ref
from app.services.trend_service import detect_trends

DEFAULT_HISTORY_LIMIT = 7


def _doc(ref) -> dict | None:
    snap = ref.get()
    return {"id": snap.id, **snap.to_dict()} if snap.exists else None


def _trim_check(check: dict) -> dict:
    return {
        "id": check.get("id"),
        "period": check.get("period"),
        "recorded_at": check.get("recorded_at"),
        "bird_count": check.get("bird_count"),
        "mortality": check.get("mortality"),
        "sick_or_injured": check.get("sick_or_injured"),
        "feed_kg": check.get("feed_kg"),
        "water_level": check.get("water_level"),
        "water_liters": check.get("water_liters"),
        "activity": check.get("activity"),
        "feeding_behaviour": check.get("feeding_behaviour"),
        "crowding_observed": check.get("crowding_observed"),
        "unusual_sound_observed": check.get("unusual_sound_observed"),
        "risk_score": check.get("risk_score"),
        "risk_status": check.get("risk_status"),
        "previous_risk_score": check.get("previous_risk_score"),
        "risk_change": check.get("risk_change"),
        "notes": check.get("notes"),
    }


def _trim_alert(alert: dict) -> dict:
    return {
        "id": alert.get("id"),
        "house_id": alert.get("house_id"),
        "status": alert.get("status"),
        "score": alert.get("score"),
        "previous_risk_score": alert.get("previous_risk_score"),
        "risk_change": alert.get("risk_change"),
        "factors": alert.get("factors"),
        "acknowledged": alert.get("acknowledged"),
        "resolved": bool(alert.get("resolved")),
        "occurrence_count": alert.get("occurrence_count", 1),
        "created_at": alert.get("created_at"),
        "updated_at": alert.get("updated_at"),
    }


def _trim_inspection(inspection: dict) -> dict:
    return {
        "id": inspection.get("id"),
        "finding_category": inspection.get("finding_category"),
        "findings": inspection.get("findings"),
        "action_taken": inspection.get("action_taken"),
        "performed_by": inspection.get("performed_by"),
        "created_at": inspection.get("created_at"),
        "alert_id": inspection.get("alert_id"),
    }


def resolve_house(houses: list[dict], name_or_id: str | None) -> dict | None:
    """Best-effort match of a farmer's free-text house reference ("House C",
    "house c", or a real house_id) against the farm's houses. None if no
    reasonable match - callers must treat that as "not available", never
    guess.
    """
    if not name_or_id:
        return None
    needle = name_or_id.strip().lower()
    for house in houses:
        if house.get("id") == name_or_id:
            return house
    for house in houses:
        if (house.get("name") or "").strip().lower() == needle:
            return house
    for house in houses:
        if needle in (house.get("name") or "").strip().lower():
            return house
    return None


def get_farm(db: Client, org_id: str, farm_id: str) -> dict | None:
    return _doc(farms_ref(db, org_id).document(farm_id))


def list_houses(db: Client, org_id: str, farm_id: str) -> list[dict]:
    return [{"id": doc.id, **doc.to_dict()} for doc in houses_ref(db, org_id, farm_id).stream()]


def get_current_flock(db: Client, org_id: str, farm_id: str, house_id: str) -> dict | None:
    docs = list(flocks_ref(db, org_id, farm_id, house_id).where("status", "==", "active").limit(1).stream())
    if docs:
        return {"id": docs[0].id, **docs[0].to_dict()}
    # Fall back to the most recently started flock if none is marked active.
    docs = list(flocks_ref(db, org_id, farm_id, house_id).stream())
    if not docs:
        return None
    latest = max(docs, key=lambda d: d.to_dict().get("start_date", ""))
    return {"id": latest.id, **latest.to_dict()}


def get_flock_history(
    db: Client, org_id: str, farm_id: str, house_id: str, limit: int = DEFAULT_HISTORY_LIMIT
) -> list[dict]:
    docs = (
        flock_checks_ref(db, org_id, farm_id, house_id)
        .order_by("recorded_at", direction=Query.DESCENDING)
        .limit(limit)
        .stream()
    )
    return [_trim_check({"id": d.id, **d.to_dict()}) for d in docs]


def get_latest_flock_check(db: Client, org_id: str, farm_id: str, house_id: str) -> dict | None:
    history = get_flock_history(db, org_id, farm_id, house_id, limit=1)
    return history[0] if history else None


def get_check_for_period_today(
    db: Client, org_id: str, farm_id: str, house_id: str, period: str, on_date: date | None = None
) -> dict | None:
    """`get_todays_morning_check` / `get_todays_evening_check` - both are this
    function with period="morning"/"evening"."""
    target_date = on_date or datetime.now(timezone.utc).date()
    for check in get_flock_history(db, org_id, farm_id, house_id, limit=20):
        if check.get("period") != period or not check.get("recorded_at"):
            continue
        recorded_date = datetime.fromisoformat(check["recorded_at"]).astimezone(timezone.utc).date()
        if recorded_date == target_date:
            return check
    return None


def get_risk_history(db: Client, org_id: str, farm_id: str, house_id: str, limit: int = DEFAULT_HISTORY_LIMIT) -> list[dict]:
    return [
        {"recorded_at": c["recorded_at"], "period": c["period"], "risk_score": c["risk_score"], "risk_status": c["risk_status"]}
        for c in get_flock_history(db, org_id, farm_id, house_id, limit)
    ]


def get_mortality_history(db: Client, org_id: str, farm_id: str, house_id: str, limit: int = DEFAULT_HISTORY_LIMIT) -> list[dict]:
    return [
        {"recorded_at": c["recorded_at"], "period": c["period"], "mortality": c["mortality"], "bird_count": c["bird_count"]}
        for c in get_flock_history(db, org_id, farm_id, house_id, limit)
    ]


def get_feed_history(db: Client, org_id: str, farm_id: str, house_id: str, limit: int = DEFAULT_HISTORY_LIMIT) -> list[dict]:
    return [
        {"recorded_at": c["recorded_at"], "period": c["period"], "feed_kg": c["feed_kg"]}
        for c in get_flock_history(db, org_id, farm_id, house_id, limit)
    ]


def get_water_history(db: Client, org_id: str, farm_id: str, house_id: str, limit: int = DEFAULT_HISTORY_LIMIT) -> list[dict]:
    return [
        {"recorded_at": c["recorded_at"], "period": c["period"], "water_level": c["water_level"], "water_liters": c["water_liters"]}
        for c in get_flock_history(db, org_id, farm_id, house_id, limit)
    ]


def get_active_alerts(db: Client, org_id: str, farm_id: str | None = None, house_id: str | None = None, limit: int = 10) -> list[dict]:
    docs = alerts_ref(db, org_id).order_by("created_at", direction=Query.DESCENDING).stream()
    alerts = [{"id": d.id, **d.to_dict()} for d in docs]
    alerts = [a for a in alerts if not a.get("resolved")]
    if farm_id:
        alerts = [a for a in alerts if a.get("farm_id") == farm_id]
    if house_id:
        alerts = [a for a in alerts if a.get("house_id") == house_id]
    return [_trim_alert(a) for a in alerts[:limit]]


def get_recent_inspections(db: Client, org_id: str, farm_id: str, house_id: str, limit: int = 5) -> list[dict]:
    docs = (
        inspections_ref(db, org_id, farm_id, house_id)
        .order_by("created_at", direction=Query.DESCENDING)
        .limit(limit)
        .stream()
    )
    return [_trim_inspection({"id": d.id, **d.to_dict()}) for d in docs]


def get_house_comparison(db: Client, org_id: str, farm_id: str) -> list[dict]:
    """Latest risk score per house in a farm, worst-first - the same shape
    the AI Health Radar uses (app/api/routes/analytics.py::compare_houses),
    reused here so Ask FlockGuard and the Radar can never disagree."""
    results = []
    for house in list_houses(db, org_id, farm_id):
        latest = get_latest_flock_check(db, org_id, farm_id, house["id"])
        results.append(
            {
                "house_id": house["id"],
                "house_name": house.get("name"),
                "risk_score": latest.get("risk_score") if latest else None,
                "risk_status": latest.get("risk_status") if latest else None,
                "last_checked_at": latest.get("recorded_at") if latest else None,
            }
        )
    results.sort(key=lambda r: (r["risk_score"] is None, -(r["risk_score"] or 0)))
    return results


def get_house_status(db: Client, org_id: str, farm_id: str, house_id: str) -> dict | None:
    house = _doc(houses_ref(db, org_id, farm_id).document(house_id))
    if not house:
        return None
    history = get_flock_history(db, org_id, farm_id, house_id, limit=DEFAULT_HISTORY_LIMIT)
    return {
        "house": house,
        "flock": get_current_flock(db, org_id, farm_id, house_id),
        "latest_check": history[0] if history else None,
        "morning_check_today": get_check_for_period_today(db, org_id, farm_id, house_id, "morning"),
        "evening_check_today": get_check_for_period_today(db, org_id, farm_id, house_id, "evening"),
        "recent_history": history,
        "active_alerts": get_active_alerts(db, org_id, farm_id, house_id),
        "recent_inspections": get_recent_inspections(db, org_id, farm_id, house_id, limit=3),
        "trend_insights": detect_trends(house_id, house.get("name") or house_id, history),
    }


def get_farm_status(db: Client, org_id: str, farm_id: str) -> dict | None:
    farm = get_farm(db, org_id, farm_id)
    if not farm:
        return None
    houses = list_houses(db, org_id, farm_id)
    comparison = get_house_comparison(db, org_id, farm_id)
    today = datetime.now(timezone.utc).date()

    missing_morning_checks = [
        house["name"]
        for house in houses
        if get_check_for_period_today(db, org_id, farm_id, house["id"], "morning", today) is None
    ]
    checked = [h for h in comparison if h["risk_score"] is not None]
    stable = [h for h in checked if h["risk_status"] == "normal"]
    needs_attention = [h for h in comparison if h["risk_status"] and h["risk_status"] != "normal"]

    all_trend_insights = []
    for house in houses:
        history = get_flock_history(db, org_id, farm_id, house["id"], limit=3)
        all_trend_insights.extend(detect_trends(house["id"], house.get("name") or house["id"], history))

    return {
        "farm": farm,
        "houses": houses,
        "house_comparison": comparison,
        "houses_total": len(houses),
        "houses_checked_today": len(checked),
        "houses_stable": len(stable),
        "houses_needing_attention": needs_attention,
        "houses_missing_morning_check": missing_morning_checks,
        "active_alerts": get_active_alerts(db, org_id, farm_id, limit=10),
        "trend_insights": all_trend_insights,
    }
