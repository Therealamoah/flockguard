from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from google.cloud.firestore import Client

from app.core.config import settings
from app.core.deps import get_current_org_id
from app.core.firestore import get_firestore_client
from app.core.limiter import limiter
from app.models.schemas import MediaUploadResponse
from app.services.cloudinary_service import upload_media
from app.services.grok_service import grok_service
from app.services.media_validation import validate_upload
from app.services.usage_service import increment_storage_bytes

router = APIRouter(prefix="/media", tags=["media"])

ALLOWED_RESOURCE_TYPES = {"image", "video"}  # Cloudinary treats audio as "video"
# What FlockGuard actually validates against (audio arrives as
# resource_type="video" per Cloudinary's convention - see media_validation.py).
_VALIDATION_KIND = {"image": "image", "video": "audio"}


@router.post("/upload", response_model=MediaUploadResponse, status_code=201)
@limiter.limit(settings.rate_limit_media_upload)
async def upload(
    request: Request,
    file: UploadFile = File(...),
    resource_type: str = "image",
    org_id: str = Depends(get_current_org_id),
    db: Client = Depends(get_firestore_client),
):
    """Uploads a Flock Check photo or audio recording to Cloudinary.

    Firestore only ever stores the returned url + public_id, never the
    binary - attach these to a Flock Check or Inspection payload.

    Validated server-side (never trust the frontend or a file extension
    alone): declared Content-Type against an allowlist, a magic-byte sniff
    of the actual bytes, and a size ceiling per media kind.
    """
    if resource_type not in ALLOWED_RESOURCE_TYPES:
        raise HTTPException(status_code=422, detail=f"resource_type must be one of {ALLOWED_RESOURCE_TYPES}")

    file_bytes = await file.read()
    validate_upload(file_bytes, file.content_type, _VALIDATION_KIND[resource_type])

    result = upload_media(file_bytes, folder=f"flockguard/{org_id}", resource_type=resource_type)
    increment_storage_bytes(db, org_id, len(file_bytes))

    transcript = None
    if resource_type == "video":  # audio - see ALLOWED_RESOURCE_TYPES comment above
        transcript = await grok_service.transcribe(file_bytes, file.filename or "voice-note", file.content_type)

    return MediaUploadResponse(**result, transcript=transcript)
