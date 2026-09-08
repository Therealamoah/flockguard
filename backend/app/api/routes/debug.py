from fastapi import APIRouter

from app.core.config import settings

router = APIRouter(prefix="/debug", tags=["debug"])


@router.get("")
def debug_info():
    """Safe debug endpoint that reports presence (not value) of Grok-related env vars.

    This endpoint is intentionally conservative: it never returns secret values,
    only booleans and configured strings to help diagnose deployment issues.
    """
    return {
        "grok_key_present": bool(settings.grok_api_key),
        "grok_api_base_url": settings.grok_api_base_url,
        "grok_model": settings.grok_model,
        "app_public_url": settings.app_public_url,
    }
