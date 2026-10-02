import httpx
import json
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

    async def stream_chat(self, messages: list[dict], *, max_tokens: int = 1500):
        """Yields the reply text piece by piece as the model writes it (an
        OpenAI-compatible SSE stream), for Ask FlockGuard's typing-style
        answers. Raises HTTPException(502) if the stream can't start; a
        stream that breaks midway just ends - the caller decides the
        fallback.

        On Groq's reasoning models (gpt-oss) the hidden "thinking" eats the
        same token budget as the answer, which is what cut answers short -
        so it's turned down and kept out of the output.
        """
        body: dict = {"model": settings.grok_model, "messages": messages, "max_tokens": max_tokens, "stream": True}
        if "groq.com" in settings.grok_api_base_url and "gpt-oss" in settings.grok_model:
            body.update(reasoning_effort="low", include_reasoning=False)
        headers = {"HTTP-Referer": settings.app_public_url, "X-Title": settings.app_name}
        if settings.grok_api_key:
            headers["Authorization"] = f"Bearer {settings.grok_api_key}"
        try:
            async with self._client.stream("POST", "/chat/completions", json=body, headers=headers, timeout=60.0) as response:
                if response.status_code != 200:
                    text = (await response.aread()).decode(errors="replace")
                    _logger.error("Grok stream returned status %s: %s", response.status_code, text[:500])
                    raise HTTPException(status_code=502, detail="Upstream Grok API error")
                async for line in response.aiter_lines():
                    if not line.startswith("data: ") or line == "data: [DONE]":
                        continue
                    try:
                        delta = json.loads(line[6:])["choices"][0]["delta"]
                    except (ValueError, KeyError, IndexError):
                        continue
                    if delta.get("content"):
                        yield delta["content"]
        except httpx.RequestError as exc:
            _logger.exception("Grok stream failed: %s", str(exc))
            raise HTTPException(status_code=502, detail="Failed to contact Grok API")

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

    async def analyze_photo(self, image_url: str) -> dict | None:
        """Gives plain-language feedback on a Flock Check photo via Groq's
        vision model, including telling the farmer when the photo doesn't
        show poultry at all.

        Best-effort and Groq-specific, same as transcribe(): returns None
        (never raises) on other providers or any failure, so a photo always
        saves. image_url is either the Cloudinary URL (uploads - Groq caps
        inline images at 4MB but our upload limit is higher) or a base64
        data: URL (Scan Flock frames, which are never stored). Like chat(),
        this describes what's visible; it must not diagnose disease.
        """
        if "groq.com" not in settings.grok_api_base_url or not settings.grok_api_key:
            return None
        # Groq's vision models don't read HEIC/HEIF (iPhone photos);
        # Cloudinary converts on delivery when the extension changes.
        for ext in (".heic", ".heif"):
            if image_url.lower().endswith(ext):
                image_url = image_url[: -len(ext)] + ".jpg"
        try:
            response = await self._client.post(
                "/chat/completions",
                headers={"Authorization": f"Bearer {settings.grok_api_key}"},
                json={
                    "model": settings.grok_vision_model,
                    "messages": [
                        {"role": "system", "content": PHOTO_REVIEW_PROMPT},
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": "Review this photo from my poultry house."},
                                {"type": "image_url", "image_url": {"url": image_url}},
                            ],
                        },
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.2,
                    "max_tokens": settings.grok_max_tokens,
                },
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            return _parse_photo_analysis(content)
        except httpx.HTTPStatusError as exc:
            # Groq's body says why (retired model, unreachable image, ...).
            _logger.error("Photo analysis failed: %s %s", exc.response.status_code, exc.response.text[:500])
            return None
        except (httpx.RequestError, ValueError, KeyError, IndexError, TypeError):
            _logger.exception("Photo analysis failed")
            return None

    async def extract_check_fields(self, transcript: str) -> dict | None:
        """Turns a voice-note transcript into Flock Check form values, so a
        farmer can speak their check instead of tapping through it.

        Returns only the fields the farmer actually mentioned (validated
        against the same enums/ranges as FlockCheckCreate) plus a one-line
        `heard` summary, or None on any failure - the transcript still lands
        in Notes either way, and the farmer reviews the form before submit.
        """
        if not settings.grok_api_key or not transcript.strip():
            return None
        try:
            response = await self._client.post(
                "/chat/completions",
                headers={"Authorization": f"Bearer {settings.grok_api_key}"},
                json={
                    "model": settings.grok_model,
                    "messages": [
                        {"role": "system", "content": VOICE_FIELDS_PROMPT},
                        {"role": "user", "content": transcript[:4000]},
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0,
                    "max_tokens": settings.grok_max_tokens,
                },
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            return _parse_check_fields(content)
        except httpx.HTTPStatusError as exc:
            _logger.error("Voice note field extraction failed: %s %s", exc.response.status_code, exc.response.text[:500])
            return None
        except (httpx.RequestError, ValueError, KeyError, IndexError, TypeError):
            _logger.exception("Voice note field extraction failed")
            return None


PHOTO_REVIEW_PROMPT = """You help poultry farmers in Ghana check on their birds from a photo.
Use short, simple sentences a farmer with little schooling can understand. No jargon.

First decide: does the photo show poultry (chickens, layers, broilers, chicks, ducks,
turkeys, guinea fowl) or their house, litter, feeders, drinkers, eggs or droppings?

Reply ONLY with a JSON object:
{
  "is_poultry": true or false,
  "summary": "one or two sentences about what you see",
  "observations": ["up to 4 short things you can see, e.g. birds look active, litter looks dry"],
  "concerns": ["up to 3 things worth checking, only if you actually see them"]
}

Rules:
- If it is NOT poultry-related, set is_poultry to false, say plainly what the photo shows,
  ask the farmer to take a clear photo of their birds, and leave observations and concerns empty.
- Only describe what is visible: posture, activity, crowding, feathers, eyes, combs,
  droppings, litter, feed and water. If the photo is too dark or blurry, say so.
- Never name a disease or give a diagnosis. For anything worrying, say what you see
  and suggest checking the birds closely or calling a vet.
- If everything looks normal, say so and leave concerns empty."""


def _parse_photo_analysis(content: str) -> dict | None:
    data = json.loads(content)
    if not isinstance(data, dict) or not isinstance(data.get("summary"), str) or not data["summary"].strip():
        return None

    def _str_list(value, limit: int) -> list[str]:
        if not isinstance(value, list):
            return []
        return [item.strip() for item in value if isinstance(item, str) and item.strip()][:limit]

    is_poultry = bool(data.get("is_poultry"))
    return {
        "is_poultry": is_poultry,
        "summary": data["summary"].strip(),
        "observations": _str_list(data.get("observations"), 4) if is_poultry else [],
        "concerns": _str_list(data.get("concerns"), 3) if is_poultry else [],
    }


VOICE_FIELDS_PROMPT = """A poultry farmer recorded a voice note during their flock check.
Pull out ONLY what they clearly said. Never guess. Leave out anything not mentioned.

Reply ONLY with a JSON object using any of these keys:
- "mortality": integer, birds that died since the last check
- "sick_or_injured": integer, birds that look sick or hurt
- "feed_kg": number, feed given in kg (convert bags only if they say the bag size)
- "water_level": "normal" | "lower" | "higher" (how much water the birds drank vs usual)
- "water_liters": number
- "activity": "normal" | "reduced" | "lethargic"
- "feeding_behaviour": "normal" | "reduced" | "none"
- "crowding_observed": true | false (birds huddling or crowding together)
- "unusual_sound_observed": true | false (coughing, sneezing, rattling, strange noises)
- "temperature_c": number
- "humidity_pct": number
- "heard": one short plain-English sentence summarising what the farmer reported

Example: "two birds died this morning, the rest are eating less and some are sneezing" ->
{"mortality": 2, "feeding_behaviour": "reduced", "unusual_sound_observed": true,
 "heard": "2 birds died, the rest are eating less and some are sneezing."}"""

_VOICE_ENUMS = {
    "water_level": {"normal", "lower", "higher"},
    "activity": {"normal", "reduced", "lethargic"},
    "feeding_behaviour": {"normal", "reduced", "none"},
}
_VOICE_INTS = ("mortality", "sick_or_injured")
_VOICE_NUMBERS = {"feed_kg": (0, 100_000), "water_liters": (0, 1_000_000), "temperature_c": (-10, 60), "humidity_pct": (0, 100)}
_VOICE_BOOLS = ("crowding_observed", "unusual_sound_observed")


def _parse_check_fields(content: str) -> dict | None:
    data = json.loads(content)
    if not isinstance(data, dict):
        return None
    fields: dict = {}
    for key in _VOICE_INTS:
        value = data.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0 and float(value).is_integer():
            fields[key] = int(value)
    for key, (low, high) in _VOICE_NUMBERS.items():
        value = data.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool) and low <= value <= high:
            fields[key] = value
    for key, allowed in _VOICE_ENUMS.items():
        if data.get(key) in allowed:
            fields[key] = data[key]
    for key in _VOICE_BOOLS:
        if isinstance(data.get(key), bool):
            fields[key] = data[key]
    if not fields:
        return None
    heard = data.get("heard")
    fields["heard"] = heard.strip() if isinstance(heard, str) and heard.strip() else None
    return fields


grok_service = GrokService()
