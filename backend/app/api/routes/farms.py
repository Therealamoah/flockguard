from fastapi import APIRouter, Depends
from google.cloud.firestore import Client

from app.core.deps import get_current_org_id
from app.core.firestore import get_firestore_client
from app.core.refs import farms_ref
from app.models.schemas import FarmCreate

router = APIRouter(prefix="/farms", tags=["farms"])


@router.get("")
def list_farms(
    org_id: str = Depends(get_current_org_id),
    db: Client = Depends(get_firestore_client),
):
    return [{"id": doc.id, **doc.to_dict()} for doc in farms_ref(db, org_id).stream()]


@router.post("", status_code=201)
def create_farm(
    payload: FarmCreate,
    org_id: str = Depends(get_current_org_id),
    db: Client = Depends(get_firestore_client),
):
    doc_ref = farms_ref(db, org_id).document()
    data = payload.model_dump()
    doc_ref.set(data)
    return {"id": doc_ref.id, **data}
