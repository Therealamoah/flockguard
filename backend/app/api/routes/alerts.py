from fastapi import APIRouter, Depends, HTTPException
from google.cloud.firestore import Client, Query

from app.core.deps import get_current_org_id
from app.core.firestore import get_firestore_client
from app.core.refs import alerts_ref

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("")
def list_alerts(
    acknowledged: bool | None = None,
    org_id: str = Depends(get_current_org_id),
    db: Client = Depends(get_firestore_client),
):
    # Filtered in Python rather than with a Firestore `.where(...)` alongside
    # `.order_by("created_at")` on a different field - that combination needs
    # a composite index that doesn't exist in this project and would 500.
    query = alerts_ref(db, org_id).order_by("created_at", direction=Query.DESCENDING)
    docs = [{"id": doc.id, **doc.to_dict()} for doc in query.stream()]
    if acknowledged is not None:
        docs = [doc for doc in docs if doc.get("acknowledged") == acknowledged]
    return docs


@router.post("/{alert_id}/acknowledge")
def acknowledge_alert(
    alert_id: str,
    org_id: str = Depends(get_current_org_id),
    db: Client = Depends(get_firestore_client),
):
    doc_ref = alerts_ref(db, org_id).document(alert_id)
    if not doc_ref.get().exists:
        raise HTTPException(status_code=404, detail="Alert not found")
    doc_ref.update({"acknowledged": True})
    return {"id": alert_id, "acknowledged": True}
