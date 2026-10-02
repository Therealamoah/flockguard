from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from google.cloud.firestore import Client

from app.core.deps import get_current_org_id
from app.core.firestore import get_firestore_client
from app.core.refs import flocks_ref, houses_ref
from app.models.schemas import FlockCountReconcile, FlockCreate, FlockStatus, FlockUpdate
from app.services.billing_service import get_subscription
from app.services.usage_service import count_birds, enforce_limit

router = APIRouter(prefix="/farms/{farm_id}/houses/{house_id}/flocks", tags=["flocks"])


@router.get("")
def list_flocks(
    farm_id: str,
    house_id: str,
    org_id: str = Depends(get_current_org_id),
    db: Client = Depends(get_firestore_client),
):
    return [{"id": doc.id, **doc.to_dict()} for doc in flocks_ref(db, org_id, farm_id, house_id).stream()]


@router.post("", status_code=201)
def create_flock(
    farm_id: str,
    house_id: str,
    payload: FlockCreate,
    org_id: str = Depends(get_current_org_id),
    db: Client = Depends(get_firestore_client),
):
    if not houses_ref(db, org_id, farm_id).document(house_id).get().exists:
        raise HTTPException(status_code=404, detail="House not found")

    subscription = get_subscription(db, org_id)
    projected_birds = count_birds(db, org_id) + payload.initial_bird_count
    enforce_limit(
        projected_birds,
        subscription.get("limits", {}).get("birds"),
        resource="bird",
        plan=subscription.get("plan", "pilot"),
    )

    doc_ref = flocks_ref(db, org_id, farm_id, house_id).document()
    data = {
        **payload.model_dump(mode="json"),
        "status": FlockStatus.ACTIVE,
        "created_at": datetime.now(timezone.utc).isoformat(),
        # Running count, decremented by mortality on each Flock Check
        # (app/api/routes/flock_checks.py::submit_flock_check) - seeded from
        # the placement-day snapshot.
        "current_bird_count": payload.initial_bird_count,
    }
    doc_ref.set(data)
    return {"id": doc_ref.id, **data}


@router.get("/{flock_id}")
def get_flock(
    farm_id: str,
    house_id: str,
    flock_id: str,
    org_id: str = Depends(get_current_org_id),
    db: Client = Depends(get_firestore_client),
):
    doc = flocks_ref(db, org_id, farm_id, house_id).document(flock_id).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Flock not found")
    return {"id": doc.id, **doc.to_dict()}


@router.patch("/{flock_id}")
def update_flock(
    farm_id: str,
    house_id: str,
    flock_id: str,
    payload: FlockUpdate,
    org_id: str = Depends(get_current_org_id),
    db: Client = Depends(get_firestore_client),
):
    doc_ref = flocks_ref(db, org_id, farm_id, house_id).document(flock_id)
    if not doc_ref.get().exists:
        raise HTTPException(status_code=404, detail="Flock not found")
    doc_ref.update(payload.model_dump(mode="json"))
    return {"id": flock_id, **payload.model_dump(mode="json")}


@router.post("/{flock_id}/reconcile-count")
def reconcile_flock_count(
    farm_id: str,
    house_id: str,
    flock_id: str,
    payload: FlockCountReconcile,
    org_id: str = Depends(get_current_org_id),
    db: Client = Depends(get_firestore_client),
):
    """Manual correction of a flock's running bird count after a physical
    recount - independent of (and doesn't touch) the Flock Check history,
    which stays an untouched log of what was recorded on each visit."""
    doc_ref = flocks_ref(db, org_id, farm_id, house_id).document(flock_id)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Flock not found")

    previous_count = doc.to_dict().get("current_bird_count")
    doc_ref.update(
        {
            "current_bird_count": payload.current_bird_count,
            "last_reconciled_at": datetime.now(timezone.utc).isoformat(),
            "last_reconciliation_reason": payload.reason,
            "last_reconciliation_previous_count": previous_count,
        }
    )
    return {"id": flock_id, "current_bird_count": payload.current_bird_count}
