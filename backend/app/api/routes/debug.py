from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
import logging

from app.core.config import settings
from app.services.grok_service import grok_service

_logger = logging.getLogger(__name__)

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


@router.get("/grok_test")
async def grok_test():
    """Performs a single test call to the upstream Grok/OpenRouter API using the
    deployed key. Returns status and a trimmed snippet of the response when
    successful. Does not return any secrets.
    """
    try:
        # Use a minimal chat call; grok_service.chat will raise HTTPException on upstream errors
        answer = await grok_service.chat([{"role": "user", "content": "ping"}])
        return {"ok": True, "sample": answer[:400]}
    except HTTPException as exc:
        # Return the status and message without revealing sensitive headers
        return JSONResponse(status_code=502, content={"ok": False, "detail": exc.detail})
    except Exception as exc:  # pragma: no cover - runtime safeguard
        _logger.exception("grok_test unexpected failure")
        return JSONResponse(status_code=502, content={"ok": False, "error": str(exc)})
