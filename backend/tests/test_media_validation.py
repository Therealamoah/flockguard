import pytest
from fastapi import HTTPException

from app.services.media_validation import validate_upload

PNG_HEAD = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
JPEG_HEAD = b"\xff\xd8\xff" + b"\x00" * 20


def test_valid_png_passes():
    validate_upload(PNG_HEAD, "image/png", "image")  # should not raise


def test_empty_file_rejected():
    with pytest.raises(HTTPException) as exc:
        validate_upload(b"", "image/png", "image")
    assert exc.value.status_code == 422


def test_wrong_content_type_rejected():
    with pytest.raises(HTTPException) as exc:
        validate_upload(PNG_HEAD, "application/pdf", "image")
    assert exc.value.status_code == 422


def test_bytes_not_matching_any_known_signature_rejected():
    fake = b"not a real image" + b"\x00" * 20
    with pytest.raises(HTTPException):
        validate_upload(fake, "image/png", "image")


def test_oversized_file_rejected():
    huge = JPEG_HEAD + b"\x00" * (9 * 1024 * 1024)  # over the 8MB image default
    with pytest.raises(HTTPException) as exc:
        validate_upload(huge, "image/jpeg", "image")
    assert "too large" in exc.value.detail.lower()
