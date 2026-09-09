"""Turns a Risk Engine result into a persisted alert - without flooding.

Previously this created a brand-new alert document on every single
watch/warning/critical check, even if the house already had one open. A
house sitting at "watch" for ten checks in a row produced ten separate
alerts. Now: at most one open alert per house at a time - it's created
once and then updated in place (score, factors, occurrence_count) as long
as the house stays alert-worthy, and is resolved (not deleted) once risk
returns to normal or a farmer files a resolving inspection.

Alert lifecycle fields:
    acknowledged   - farmer has seen it (existing field, unchanged meaning)
    resolved       - the underlying issue is done (auto, on return to
                     normal risk, or manually via a linked inspection)
    resolved_at / resolution_reason - set when resolved
    occurrence_count - how many consecutive alert-worthy checks fed this alert
    previous_risk_score / risk_change - carried over from the triggering check
    latest_check_id - most recent check that touched this alert
                     (flock_check_id remains the check that *first* opened it)
"""

from datetime import datetime, timezone

from google.cloud.firestore import Client

from app.core.refs import alerts_ref
from app.risk_engine.models import RiskResult
from app.risk_engine.status import NORMAL

ALERT_WORTHY_STATUSES = {"watch", "warning", "critical"}


def _is_open(alert: dict) -> bool:
    # Older alert docs (pre-dedup) have no `resolved` field at all - treat
    # that as "not resolved" so this still recognizes them as open.
    return not alert.get("resolved")


def _find_open_alert_for_house(db: Client, org_id: str, house_id: str) -> tuple[str, dict] | None:
    docs = list(alerts_ref(db, org_id).where("house_id", "==", house_id).stream())
    open_alerts = [(doc.id, doc.to_dict()) for doc in docs if _is_open(doc.to_dict())]
    if not open_alerts:
        return None
    # Most recently created, if more than one somehow exists (e.g. legacy data).
    return max(open_alerts, key=lambda pair: pair[1].get("created_at", ""))


def sync_alert_for_check(
    db: Client,
    *,
    org_id: str,
    farm_id: str,
    house_id: str,
    flock_id: str | None,
    flock_check_id: str,
    risk: RiskResult,
    previous_risk_score: int | None,
) -> dict | None:
    """Creates, updates, or resolves the house's alert based on this check's
    risk result. Returns {"action": "created"|"updated"|"resolved", "alert": {...}}
    or None if risk is normal and there was no open alert to resolve.
    """
    now = datetime.now(timezone.utc).isoformat()
    existing = _find_open_alert_for_house(db, org_id, house_id)
    risk_change = risk.score - previous_risk_score if previous_risk_score is not None else None

    if risk.status == NORMAL:
        if existing is None:
            return None
        alert_id, alert = existing
        doc_ref = alerts_ref(db, org_id).document(alert_id)
        updates = {
            "resolved": True,
            "resolved_at": now,
            "resolution_reason": "risk_returned_to_normal",
            "updated_at": now,
            "latest_check_id": flock_check_id,
            "score": risk.score,
            "status": risk.status,
        }
        doc_ref.update(updates)
        return {"action": "resolved", "alert": {"id": alert_id, **alert, **updates}}

    if risk.status not in ALERT_WORTHY_STATUSES:
        return None

    if existing is not None:
        alert_id, alert = existing
        doc_ref = alerts_ref(db, org_id).document(alert_id)
        updates = {
            "score": risk.score,
            "status": risk.status,
            "factors": [f.model_dump() for f in risk.factors],
            "previous_risk_score": previous_risk_score,
            "risk_change": risk_change,
            "updated_at": now,
            "latest_check_id": flock_check_id,
            "flock_id": flock_id,
            "occurrence_count": alert.get("occurrence_count", 1) + 1,
        }
        doc_ref.update(updates)
        return {"action": "updated", "alert": {"id": alert_id, **alert, **updates}}

    alert = {
        "org_id": org_id,
        "farm_id": farm_id,
        "house_id": house_id,
        "flock_id": flock_id,
        "flock_check_id": flock_check_id,
        "latest_check_id": flock_check_id,
        "score": risk.score,
        "status": risk.status,
        "factors": [f.model_dump() for f in risk.factors],
        "previous_risk_score": previous_risk_score,
        "risk_change": risk_change,
        "created_at": now,
        "updated_at": now,
        "acknowledged": False,
        "resolved": False,
        "resolved_at": None,
        "resolution_reason": None,
        "occurrence_count": 1,
    }
    doc_ref = alerts_ref(db, org_id).document()
    doc_ref.set(alert)
    return {"action": "created", "alert": {"id": doc_ref.id, **alert}}


# Kept as a thin backward-compatible alias - nothing outside this module
# and its tests should need to know the function was renamed/expanded.
def maybe_create_alert(
    db: Client,
    *,
    org_id: str,
    farm_id: str,
    house_id: str,
    flock_check_id: str,
    risk: RiskResult,
) -> dict | None:
    result = sync_alert_for_check(
        db,
        org_id=org_id,
        farm_id=farm_id,
        house_id=house_id,
        flock_id=None,
        flock_check_id=flock_check_id,
        risk=risk,
        previous_risk_score=None,
    )
    return result["alert"] if result else None
