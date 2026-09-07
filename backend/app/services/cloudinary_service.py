import cloudinary
import cloudinary.uploader

from app.core.config import settings

cloudinary.config(
    cloud_name=settings.cloudinary_cloud_name,
    api_key=settings.cloudinary_api_key,
    api_secret=settings.cloudinary_api_secret,
    secure=True,
)


def upload_media(file_bytes: bytes, folder: str, resource_type: str = "image") -> dict:
    """Uploads a flock photo/audio file and returns its Cloudinary reference."""
    result = cloudinary.uploader.upload(
        file_bytes,
        folder=folder,
        resource_type=resource_type,
    )
    return {
        "url": result["secure_url"],
        "public_id": result["public_id"],
    }
