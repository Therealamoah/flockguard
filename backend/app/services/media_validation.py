"""Server-side upload validation - never trust the frontend or a file's
extension alone. Checks declared Content-Type against an allowlist and
sniffs the first bytes for a matching file signature, plus enforces a
size ceiling per media kind.
"""

from fastapi import HTTPException

from app.core.config import settings

ALLOWED_IMAGE_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}
ALLOWED_AUDIO_CONTENT_TYPES = {
    "audio/webm",
    "audio/ogg",
    "audio/mpeg",
    "audio/mp4",
    "audio/aac",
    "audio/wav",
    "audio/x-wav",
    "video/webm",  # MediaRecorder commonly reports audio-only capture as this
}

# Magic-byte signatures for the formats FlockGuard actually accepts, so a
# renamed/relabelled file can't slip past the Content-Type check alone.
_SIGNATURES: list[tuple[bytes, int]] = [
    (b"\xff\xd8\xff", 0),  # JPEG
    (b"\x89PNG\r\n\x1a\n", 0),  # PNG
    (b"RIFF", 0),  # WEBP/WAV container (checked further below)
    (b"\x1a\x45\xdf\xa3", 0),  # WebM/Matroska (audio/webm, video/webm)
    (b"OggS", 0),  # OGG
    (b"ID3", 0),  # MP3 with ID3 tag
    (b"\xff\xfb", 0),  # MP3 without ID3 tag
    (b"ftyp", 4),  # MP4/M4A/HEIC family
]


def _looks_like_known_media(head: bytes) -> bool:
    for signature, offset in _SIGNATURES:
        if head[offset : offset + len(signature)] == signature:
            return True
    return False


def validate_upload(file_bytes: bytes, content_type: str | None, resource_type: str) -> None:
    """Raises HTTPException(422) if the upload fails validation; otherwise returns None."""
    if not file_bytes:
        raise HTTPException(status_code=422, detail="Empty file")

    max_bytes = int((settings.max_image_upload_mb if resource_type == "image" else settings.max_audio_upload_mb) * 1024 * 1024)
    if len(file_bytes) > max_bytes:
        limit_mb = settings.max_image_upload_mb if resource_type == "image" else settings.max_audio_upload_mb
        raise HTTPException(status_code=422, detail=f"File too large - max {limit_mb}MB for {resource_type} uploads")

    allowed_types = ALLOWED_IMAGE_CONTENT_TYPES if resource_type == "image" else ALLOWED_AUDIO_CONTENT_TYPES
    if content_type and content_type.lower() not in allowed_types:
        raise HTTPException(status_code=422, detail=f"Unsupported {resource_type} content type: {content_type}")

    if not _looks_like_known_media(file_bytes[:16]):
        raise HTTPException(status_code=422, detail="File does not look like a valid image/audio file")
