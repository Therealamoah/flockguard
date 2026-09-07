from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.core.deps import get_current_org_id
from app.models.schemas import MediaUploadResponse
from app.services.cloudinary_service import upload_media

router = APIRouter(prefix="/media", tags=["media"])

ALLOWED_RESOURCE_TYPES = {"image", "video"}  # Cloudinary treats audio as "video"


@router.post("/upload", response_model=MediaUploadResponse, status_code=201)
async def upload(
    file: UploadFile = File(...),
    resource_type: str = "image",
    org_id: str = Depends(get_current_org_id),
):
    """Uploads a Flock Check photo or audio recording to Cloudinary.

    Firestore only ever stores the returned url + public_id, never the
    binary - attach these to a Flock Check or Inspection payload.
    """
    if resource_type not in ALLOWED_RESOURCE_TYPES:
        raise HTTPException(status_code=422, detail=f"resource_type must be one of {ALLOWED_RESOURCE_TYPES}")

    file_bytes = await file.read()
    result = upload_media(file_bytes, folder=f"flockguard/{org_id}", resource_type=resource_type)
    return MediaUploadResponse(**result)
