import httpx
import logging
from fastapi import HTTPException

from app.core.config import settings


_logger = logging.getLogger(__name__)


class GrokService:
    """Thin wrapper around the Grok API. The API key never leaves the backend.

    Grok explains what the Risk Engine already found - it does not compute
    risk scores itself and must not be presented as a disease-diagnosis tool.
    """

    def __init__(self) -> None:
        # Create a reusable client but build Authorization and other
        # per-request headers at call-time so logs and errors can show the
        # current configuration. Note: Settings are still read at startup by
        # pydantic; updating env vars in the host requires a restart to change
        # `settings` values.
        self._client = httpx.AsyncClient(base_url=settings.grok_api_base_url, timeout=30.0)

    async def chat(self, messages: list[dict], model: str | None = None) -> str:
        try:
            # Build per-request headers (do not log the key itself).
            auth_header = f"Bearer {settings.grok_api_key}" if settings.grok_api_key else None
            has_auth = bool(auth_header)
            _logger.debug(
                "Grok request preparing: has_auth_header=%s base_url=%s model=%s",
                has_auth,
                self._client.base_url,
                model or settings.grok_model,
            )

            headers = {
                "HTTP-Referer": settings.app_public_url,
                "X-Title": settings.app_name,
            }
            if auth_header:
                headers["Authorization"] = auth_header

            response = await self._client.post(
                "/chat/completions",
                json={
                    "model": model or settings.grok_model,
                    "messages": messages,
                    "max_tokens": settings.grok_max_tokens,
                },
                headers=headers,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            # Log full response body server-side (trimmed) then raise a 502
            text = exc.response.text if exc.response is not None else str(exc)
            _logger.exception("Grok API returned status %s: %s", getattr(exc.response, "status_code", "?"), text[:1000])
            # Also log the request headers we sent (mask Authorization)
            try:
                req_headers = dict(exc.request.headers) if exc.request is not None else {}
                if "authorization" in (k.lower() for k in req_headers):
                    # mask the header value
                    for k in list(req_headers.keys()):
                        if k.lower() == "authorization":
                            req_headers[k] = "***MASKED***"
                _logger.warning("Grok request headers (masked): %s", req_headers)
            except Exception:
                _logger.warning("Could not read request headers for Grok error")

            raise HTTPException(status_code=502, detail="Upstream Grok API error")
        except httpx.RequestError as exc:
            _logger.exception("Failed to contact Grok API: %s", str(exc))
            raise HTTPException(status_code=502, detail="Failed to contact Grok API")

        data = response.json()
        return data["choices"][0]["message"]["content"]


grok_service = GrokService()
