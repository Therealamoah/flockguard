from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from google.cloud.firestore import Client, Query

from app.core.deps import get_current_org_id
from app.core.firestore import get_firestore_client
from app.core.refs import alerts_ref

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("")
def list_alerts(
    acknowledged: bool | None = None,
    resolved: bool | None = None,
    org_id: str = Depends(get_current_org_id),
    db: Client = Depends(get_firestore_client),
):
    """`resolved` is the meaningful "is this alert actually done" filter
    (auto-set when risk returns to normal, or when a linked inspection
    resolves it - see app/services/alert_engine.py and
    app/api/routes/inspections.py). `acknowledged` is kept for backward
    compatibility and just means "a farmer has seen it" - a house can stay
    unresolved even after being acknowledged if the underlying risk persists.
    """
    # Filtered in Python rather than with a Firestore `.where(...)` alongside
    # `.order_by("created_at")` on a different field - that combination needs
    # a composite index that doesn't exist in this project and would 500.
    query = alerts_ref(db, org_id).order_by("created_at", direction=Query.DESCENDING)
    docs = [{"id": doc.id, **doc.to_dict()} for doc in query.stream()]
    if acknowledged is not None:
        docs = [doc for doc in docs if doc.get("acknowledged") == acknowledged]
    if resolved is not None:
        # Older alert docs (pre-dedup) have no `resolved` field - treat
        # that as "not resolved" so they still show up as open.
        docs = [doc for doc in docs if bool(doc.get("resolved")) == resolved]
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


@router.post("/{alert_id}/resolve")
def resolve_alert(
    alert_id: str,
    org_id: str = Depends(get_current_org_id),
    db: Client = Depends(get_firestore_client),
):
    """Manual resolution without a full inspection record (e.g. the farmer
    is confident it was a one-off and wants to clear it). Prefer recording
    an inspection (POST .../inspections) when there's an actual finding to
    keep - that's what builds useful history for "what did we find last
    time this house was flagged?"."""
    doc_ref = alerts_ref(db, org_id).document(alert_id)
    if not doc_ref.get().exists:
        raise HTTPException(status_code=404, detail="Alert not found")
    now = datetime.now(timezone.utc).isoformat()
    updates = {
        "acknowledged": True,
        "resolved": True,
        "resolved_at": now,
        "resolution_reason": "manually_resolved",
        "updated_at": now,
    }
    doc_ref.update(updates)
    return {"id": alert_id, **updates}
