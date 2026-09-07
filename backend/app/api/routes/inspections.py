from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from google.cloud.firestore import Client, Query

from app.core.deps import get_current_org_id
from app.core.firestore import get_firestore_client
from app.core.refs import alerts_ref, inspections_ref
from app.models.schemas import InspectionCreate

router = APIRouter(prefix="/farms/{farm_id}/houses/{house_id}/inspections", tags=["inspections"])


@router.get("")
def list_inspections(
    farm_id: str,
    house_id: str,
    org_id: str = Depends(get_current_org_id),
    db: Client = Depends(get_firestore_client),
):
    docs = (
        inspections_ref(db, org_id, farm_id, house_id)
        .order_by("created_at", direction=Query.DESCENDING)
        .stream()
    )
    return [{"id": doc.id, **doc.to_dict()} for doc in docs]


@router.post("", status_code=201)
def create_inspection(
    farm_id: str,
    house_id: str,
    payload: InspectionCreate,
    org_id: str = Depends(get_current_org_id),
    db: Client = Depends(get_firestore_client),
):
    """Records an inspection outcome and, when it resolves the alert that
    triggered it, marks that alert acknowledged."""
    doc_ref = inspections_ref(db, org_id, farm_id, house_id).document()
    data = {
        **payload.model_dump(mode="json"),
        "house_id": house_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    doc_ref.set(data)

    if payload.alert_id:
        alert_doc = alerts_ref(db, org_id).document(payload.alert_id)
        if alert_doc.get().exists:
            alert_doc.update({"acknowledged": True})

    return {"id": doc_ref.id, **data}


@router.get("/{inspection_id}")
def get_inspection(
    farm_id: str,
    house_id: str,
    inspection_id: str,
    org_id: str = Depends(get_current_org_id),
    db: Client = Depends(get_firestore_client),
):
    doc = inspections_ref(db, org_id, farm_id, house_id).document(inspection_id).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Inspection not found")
    return {"id": doc.id, **doc.to_dict()}
