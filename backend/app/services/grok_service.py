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
        self._client = httpx.AsyncClient(
            base_url=settings.grok_api_base_url,
            headers={
                "Authorization": f"Bearer {settings.grok_api_key}",
                "HTTP-Referer": settings.app_public_url,
                "X-Title": settings.app_name,
            },
            timeout=30.0,
        )

    async def chat(self, messages: list[dict], model: str | None = None) -> str:
        try:
            response = await self._client.post(
                "/chat/completions",
                json={
                    "model": model or settings.grok_model,
                    "messages": messages,
                    "max_tokens": settings.grok_max_tokens,
                },
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            # Log full response body server-side (trimmed) then raise a 502
            text = exc.response.text if exc.response is not None else str(exc)
            _logger.exception("Grok API returned status %s: %s", getattr(exc.response, "status_code", "?"), text[:1000])
            raise HTTPException(status_code=502, detail="Upstream Grok API error")
        except httpx.RequestError as exc:
            _logger.exception("Failed to contact Grok API: %s", str(exc))
            raise HTTPException(status_code=502, detail="Failed to contact Grok API")

        data = response.json()
        return data["choices"][0]["message"]["content"]


grok_service = GrokService()
