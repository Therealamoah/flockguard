from fastapi import APIRouter, Depends, HTTPException
from google.cloud.firestore import Client

from app.core.deps import get_current_org_id
from app.core.firestore import get_firestore_client
from app.core.refs import farms_ref, houses_ref
from app.models.schemas import HouseCreate

router = APIRouter(prefix="/farms/{farm_id}/houses", tags=["houses"])


@router.get("")
def list_houses(
    farm_id: str,
    org_id: str = Depends(get_current_org_id),
    db: Client = Depends(get_firestore_client),
):
    return [{"id": doc.id, **doc.to_dict()} for doc in houses_ref(db, org_id, farm_id).stream()]


@router.post("", status_code=201)
def create_house(
    farm_id: str,
    payload: HouseCreate,
    org_id: str = Depends(get_current_org_id),
    db: Client = Depends(get_firestore_client),
):
    if not farms_ref(db, org_id).document(farm_id).get().exists:
        raise HTTPException(status_code=404, detail="Farm not found")
    doc_ref = houses_ref(db, org_id, farm_id).document()
    data = payload.model_dump()
    doc_ref.set(data)
    return {"id": doc_ref.id, **data}


@router.get("/{house_id}")
def get_house(
    farm_id: str,
    house_id: str,
    org_id: str = Depends(get_current_org_id),
    db: Client = Depends(get_firestore_client),
):
    doc = houses_ref(db, org_id, farm_id).document(house_id).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="House not found")
    return {"id": doc.id, **doc.to_dict()}
