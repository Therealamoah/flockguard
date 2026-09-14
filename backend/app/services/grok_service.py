import httpx
import logging
from fastapi import HTTPException

from app.core.config import settings


_logger = logging.getLogger(__name__)


class ToolCallValidationError(Exception):
    """The provider rejected a generation attempt before returning any
    message - either a tool call's arguments didn't match its schema, the
    model tried to call a tool while tool_choice="none", or its raw output
    couldn't be parsed (Groq validates/parses server-side and responds 400
    instead of passing the malformed attempt through, unlike OpenRouter/
    OpenAI). Distinct from a generic upstream failure so the agent loop can
    ask the model to retry instead of failing the whole run."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


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
        #
        # transport retries=2: this client lives for the process's entire
        # lifetime, so its pooled keep-alive connections can go stale (the
        # remote end closes an idle one, a network blip drops it) without
        # httpx noticing until the next request tries to reuse it - that
        # shows up as a ConnectTimeout/ConnectError on a request that would
        # have succeeded on a fresh connection. This only retries the
        # connection attempt itself (idempotent at the TCP/TLS level), never
        # a request that actually reached Grok and got a response.
        self._client = httpx.AsyncClient(
            base_url=settings.grok_api_base_url,
            timeout=30.0,
            transport=httpx.AsyncHTTPTransport(retries=2),
        )

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

    async def chat_completion(
        self,
        messages: list[dict],
        *,
        tools: list[dict] | None = None,
        tool_choice: str | None = None,
        response_format: dict | None = None,
        model: str | None = None,
    ) -> dict:
        """Like `chat()`, but returns the full response `message` object
        (not just its text) and supports OpenAI-compatible tool-calling -
        used by app/agent/flockguard_agent.py's investigation loop.
        OpenRouter proxies Grok models through an OpenAI-compatible
        `/chat/completions` API, including the `tools`/`tool_choice`/
        `response_format` parameters, so no new client library is needed.
        """
        try:
            auth_header = f"Bearer {settings.grok_api_key}" if settings.grok_api_key else None
            headers = {"HTTP-Referer": settings.app_public_url, "X-Title": settings.app_name}
            if auth_header:
                headers["Authorization"] = auth_header

            body: dict = {
                "model": model or settings.grok_model,
                "messages": messages,
                "max_tokens": settings.grok_max_tokens,
            }
            if tools:
                body["tools"] = tools
            if tool_choice:
                body["tool_choice"] = tool_choice
            if response_format:
                body["response_format"] = response_format

            response = await self._client.post("/chat/completions", json=body, headers=headers)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            text = exc.response.text if exc.response is not None else str(exc)
            _logger.exception(
                "Grok API returned status %s: %s", getattr(exc.response, "status_code", "?"), text[:1000]
            )
            if exc.response is not None and exc.response.status_code == 400:
                try:
                    error = exc.response.json().get("error", {})
                except ValueError:
                    error = {}
                if error.get("code") in ("tool_use_failed", "output_parse_failed"):
                    raise ToolCallValidationError(error.get("message", "Generation validation failed"))
            raise HTTPException(status_code=502, detail="Upstream Grok API error")
        except httpx.RequestError as exc:
            _logger.exception("Failed to contact Grok API: %s", str(exc))
            raise HTTPException(status_code=502, detail="Failed to contact Grok API")

        data = response.json()
        return data["choices"][0]["message"]

    async def transcribe(self, file_bytes: bytes, filename: str, content_type: str) -> str | None:
        """Transcribes a Flock Check voice note via Groq's Whisper endpoint.

        Best-effort and Groq-specific: unlike /chat/completions, audio
        transcription isn't part of the OpenAI-compatible surface every
        GROK_API_BASE_URL provider shares, so this quietly returns None on
        OpenRouter/direct-xAI instead of raising - a farmer's audio
        attachment should never fail to save just because transcription
        isn't available.
        """
        if "groq.com" not in settings.grok_api_base_url or not settings.grok_api_key:
            return None
        try:
            response = await self._client.post(
                "/audio/transcriptions",
                headers={"Authorization": f"Bearer {settings.grok_api_key}"},
                files={"file": (filename, file_bytes, content_type or "audio/webm")},
                data={"model": settings.grok_transcribe_model},
            )
            response.raise_for_status()
            return response.json().get("text", "").strip() or None
        except (httpx.HTTPStatusError, httpx.RequestError, ValueError, KeyError):
            _logger.exception("Voice note transcription failed")
            return None


grok_service = GrokService()
