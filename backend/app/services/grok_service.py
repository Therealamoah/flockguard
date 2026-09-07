import httpx

from app.core.config import settings


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
        response = await self._client.post(
            "/chat/completions",
            json={
                "model": model or settings.grok_model,
                "messages": messages,
                "max_tokens": settings.grok_max_tokens,
            },
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]


grok_service = GrokService()
