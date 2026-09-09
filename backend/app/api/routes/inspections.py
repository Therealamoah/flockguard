from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from google.cloud.firestore import Client, Query

from app.core.deps import get_current_org_id
from app.core.firebase import get_current_user
from app.core.firestore import get_firestore_client
from app.core.refs import alerts_ref, flocks_ref, inspections_ref
from app.models.schemas import FlockStatus, InspectionCreate

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


def _performed_by(user: dict) -> str:
    # Prefer a real display name if the Firebase token carries one, then
    # email, then fall back to the uid - never asks the farmer to type
    # their own name in, per the audit's Phase 7 request.
    return user.get("name") or user.get("email") or user.get("uid")


def _active_flock_id(db: Client, org_id: str, farm_id: str, house_id: str) -> str | None:
    docs = flocks_ref(db, org_id, farm_id, house_id).where("status", "==", FlockStatus.ACTIVE.value).limit(1).stream()
    return next((doc.id for doc in docs), None)


def _open_alert_id_for_house(db: Client, org_id: str, house_id: str) -> str | None:
    docs = alerts_ref(db, org_id).where("house_id", "==", house_id).stream()
    open_alerts = [(doc.id, doc.to_dict()) for doc in docs if not doc.to_dict().get("resolved")]
    if not open_alerts:
        return None
    return max(open_alerts, key=lambda pair: pair[1].get("created_at", ""))[0]


@router.post("", status_code=201)
def create_inspection(
    farm_id: str,
    house_id: str,
    payload: InspectionCreate,
    org_id: str = Depends(get_current_org_id),
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_firestore_client),
):
    """Records a structured inspection outcome and, when it resolves the
    alert that prompted it, marks that alert resolved (not just
    acknowledged) - closing the loop from AI/Risk warning -> human
    inspection -> recorded outcome -> resolved alert.
    """
    now = datetime.now(timezone.utc).isoformat()
    alert_id = payload.alert_id or _open_alert_id_for_house(db, org_id, house_id)

    doc_ref = inspections_ref(db, org_id, farm_id, house_id).document()
    data = {
        **payload.model_dump(mode="json"),
        "house_id": house_id,
        "flock_id": _active_flock_id(db, org_id, farm_id, house_id),
        "alert_id": alert_id,
        "performed_by": _performed_by(user),
        "created_at": now,
    }
    doc_ref.set(data)

    if alert_id:
        alert_doc = alerts_ref(db, org_id).document(alert_id)
        if alert_doc.get().exists:
            alert_doc.update(
                {
                    "acknowledged": True,
                    "resolved": True,
                    "resolved_at": now,
                    "resolution_reason": "inspection_completed",
                    "resolving_inspection_id": doc_ref.id,
                    "updated_at": now,
                }
            )

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
