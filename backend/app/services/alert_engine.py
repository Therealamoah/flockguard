"""Turns a Risk Engine result into a persisted alert when risk is worth flagging."""

from datetime import datetime, timezone

from google.cloud.firestore import Client

from app.core.refs import alerts_ref
from app.risk_engine.models import RiskResult
from app.risk_engine.status import NORMAL

ALERT_WORTHY_STATUSES = {"watch", "warning", "critical"}


def maybe_create_alert(
    db: Client,
    *,
    org_id: str,
    farm_id: str,
    house_id: str,
    flock_check_id: str,
    risk: RiskResult,
) -> dict | None:
    if risk.status == NORMAL:
        return None
    if risk.status not in ALERT_WORTHY_STATUSES:
        return None

    alert = {
        "org_id": org_id,
        "farm_id": farm_id,
        "house_id": house_id,
        "flock_check_id": flock_check_id,
        "score": risk.score,
        "status": risk.status,
        "factors": [f.model_dump() for f in risk.factors],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "acknowledged": False,
    }

    doc_ref = alerts_ref(db, org_id).document()
    doc_ref.set(alert)

    return {"id": doc_ref.id, **alert}
