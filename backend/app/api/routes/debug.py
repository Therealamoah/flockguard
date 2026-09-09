from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
import logging

from app.core.config import settings
from app.core.firebase import get_current_user
from app.services.grok_service import grok_service

_logger = logging.getLogger(__name__)

router = APIRouter(prefix="/debug", tags=["debug"])


def _require_non_production() -> None:
    """Debug routes are diagnostic tooling, not a production feature.

    They previously had no auth dependency at all, which let anyone who
    could reach the backend trigger real, billed Grok/OpenRouter calls.
    Now they require a valid Firebase session AND refuse to run at all in
    production, regardless of who's asking - so a leaked/expired
    ENVIRONMENT misconfiguration doesn't reopen the hole.
    """
    if settings.is_production:
        raise HTTPException(status_code=404, detail="Not found")


@router.get("", dependencies=[Depends(get_current_user)])
def debug_info():
    """Safe debug endpoint that reports presence (not value) of Grok-related env vars.

    This endpoint is intentionally conservative: it never returns secret values,
    only booleans and configured strings to help diagnose deployment issues.
    Requires authentication and is disabled outright when ENVIRONMENT=production.
    """
    _require_non_production()
    return {
        "environment": settings.environment,
        "grok_key_present": bool(settings.grok_api_key),
        "grok_api_base_url": settings.grok_api_base_url,
        "grok_model": settings.grok_model,
        "app_public_url": settings.app_public_url,
    }


@router.get("/grok_test", dependencies=[Depends(get_current_user)])
async def grok_test():
    """Performs a single test call to the upstream Grok/OpenRouter API using the
    deployed key. Returns status and a trimmed snippet of the response when
    successful. Does not return any secrets.

    Requires authentication and is disabled outright when ENVIRONMENT=production,
    since every call here is a real, billed AI request.
    """
    _require_non_production()
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
