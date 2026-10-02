import base64

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from google.cloud.firestore import Client

from app.core.config import settings
from app.core.deps import get_current_org_id
from app.core.firestore import get_firestore_client
from app.core.limiter import limiter
from app.models.schemas import FlockScanResponse, MediaUploadResponse
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
    analyze: bool = True,
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
    voice_fields = None
    photo_analysis = None
    if resource_type == "video":  # audio - see ALLOWED_RESOURCE_TYPES comment above
        transcript = await grok_service.transcribe(file_bytes, file.filename or "voice-note", file.content_type)
        if transcript:
            voice_fields = await grok_service.extract_check_fields(transcript)
    elif analyze:  # analyze=false: a Scan Flock frame the farmer already had reviewed via /scan
        photo_analysis = await grok_service.analyze_photo(result["url"])

    return MediaUploadResponse(**result, transcript=transcript, voice_fields=voice_fields, photo_analysis=photo_analysis)


# Groq caps inline (base64) images at 4MB; base64 inflates by ~4/3, so 3MB
# raw is the most that fits. The Scan Flock camera sends a downscaled JPEG
# frame (typically a few hundred KB), so this only rejects abuse.
_MAX_SCAN_BYTES = 3 * 1024 * 1024
_SCAN_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}


@router.post("/scan", response_model=FlockScanResponse)
@limiter.limit(settings.rate_limit_flock_scan)
async def scan(
    request: Request,
    file: UploadFile = File(...),
    org_id: str = Depends(get_current_org_id),
):
    """AI camera "Scan Flock": reviews one camera frame without storing it.

    Unlike /upload, nothing goes to Cloudinary - a farmer may rescan many
    times while pointing the phone around, and only the frame they choose to
    attach to a Flock Check is uploaded (through /upload) and kept.
    """
    file_bytes = await file.read()
    validate_upload(file_bytes, file.content_type, "image")
    content_type = (file.content_type or "").lower()
    if content_type not in _SCAN_CONTENT_TYPES:
        raise HTTPException(status_code=422, detail="Scan frames must be JPEG, PNG or WEBP")
    if len(file_bytes) > _MAX_SCAN_BYTES:
        raise HTTPException(status_code=422, detail="Scan frame too large - max 3MB")

    data_url = f"data:{content_type};base64,{base64.b64encode(file_bytes).decode()}"
    analysis = await grok_service.analyze_photo(data_url)
    return FlockScanResponse(available=analysis is not None, analysis=analysis)
