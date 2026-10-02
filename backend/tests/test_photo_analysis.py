import asyncio
import json

import httpx
import pytest

from app.services import grok_service as grok_module
from app.services.grok_service import GrokService, _parse_photo_analysis


def test_parse_poultry_photo_trims_and_caps_lists():
    result = _parse_photo_analysis(
        json.dumps(
            {
                "is_poultry": True,
                "summary": "  Healthy-looking broilers.  ",
                "observations": ["a", "b", "c", "d", "e", "", 5],
                "concerns": ["wet litter"],
            }
        )
    )
    assert result == {
        "is_poultry": True,
        "summary": "Healthy-looking broilers.",
        "observations": ["a", "b", "c", "d"],
        "concerns": ["wet litter"],
    }


def test_parse_non_poultry_photo_drops_observations():
    result = _parse_photo_analysis(
        json.dumps({"is_poultry": False, "summary": "This is a photo of a car.", "observations": ["red car"]})
    )
    assert result["is_poultry"] is False
    assert result["observations"] == [] and result["concerns"] == []


def test_parse_rejects_missing_summary():
    assert _parse_photo_analysis(json.dumps({"is_poultry": True})) is None


def test_parse_invalid_json_raises_value_error():
    with pytest.raises(ValueError):
        _parse_photo_analysis("not json")


def test_analyze_photo_noops_when_not_groq(monkeypatch):
    monkeypatch.setattr(grok_module.settings, "grok_api_base_url", "https://openrouter.ai/api/v1")
    monkeypatch.setattr(grok_module.settings, "grok_api_key", "key")
    assert asyncio.run(GrokService().analyze_photo("https://res.cloudinary.com/x.jpg")) is None


def _service_with_handler(monkeypatch, handler):
    monkeypatch.setattr(grok_module.settings, "grok_api_base_url", "https://api.groq.com/openai/v1")
    monkeypatch.setattr(grok_module.settings, "grok_api_key", "key")
    service = GrokService()
    service._client = httpx.AsyncClient(base_url="https://api.groq.com/openai/v1", transport=httpx.MockTransport(handler))
    return service


def test_analyze_photo_sends_image_and_converts_heic(monkeypatch):
    sent = {}

    def handler(request):
        sent["body"] = json.loads(request.content)
        content = json.dumps({"is_poultry": True, "summary": "Birds look active.", "observations": [], "concerns": []})
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    service = _service_with_handler(monkeypatch, handler)
    result = asyncio.run(service.analyze_photo("https://res.cloudinary.com/demo/image/upload/v1/pic.HEIC"))

    assert result["summary"] == "Birds look active."
    image_part = sent["body"]["messages"][1]["content"][1]
    assert image_part["image_url"]["url"] == "https://res.cloudinary.com/demo/image/upload/v1/pic.jpg"
    assert sent["body"]["model"] == grok_module.settings.grok_vision_model


def test_analyze_photo_returns_none_on_upstream_error(monkeypatch):
    service = _service_with_handler(monkeypatch, lambda request: httpx.Response(500, text="boom"))
    assert asyncio.run(service.analyze_photo("https://res.cloudinary.com/x.jpg")) is None


JPEG_FRAME = b"\xff\xd8\xff" + b"\x00" * 64


def test_scan_returns_analysis_without_uploading(authed_client, monkeypatch):
    seen = {}

    async def fake_analyze(image_url):
        seen["url"] = image_url
        return {"is_poultry": True, "summary": "Birds look active.", "observations": [], "concerns": []}

    def no_upload(*args, **kwargs):
        raise AssertionError("Scan frames must never be stored in Cloudinary")

    monkeypatch.setattr("app.services.grok_service.grok_service.analyze_photo", fake_analyze)
    monkeypatch.setattr("app.api.routes.media.upload_media", no_upload)

    response = authed_client.post("/media/scan", files={"file": ("frame.jpg", JPEG_FRAME, "image/jpeg")})

    assert response.status_code == 200
    assert response.json()["available"] is True
    assert response.json()["analysis"]["summary"] == "Birds look active."
    assert seen["url"].startswith("data:image/jpeg;base64,")


def test_scan_reports_unavailable_when_ai_returns_nothing(authed_client):
    # conftest's default analyze_photo stub returns None
    response = authed_client.post("/media/scan", files={"file": ("frame.jpg", JPEG_FRAME, "image/jpeg")})
    assert response.status_code == 200
    assert response.json() == {"available": False, "analysis": None}


def test_scan_rejects_heic(authed_client):
    heic = b"\x00\x00\x00\x18ftypheic" + b"\x00" * 32
    response = authed_client.post("/media/scan", files={"file": ("frame.heic", heic, "image/heic")})
    assert response.status_code == 422


def test_scan_requires_auth(client):
    response = client.post("/media/scan", files={"file": ("frame.jpg", JPEG_FRAME, "image/jpeg")})
    assert response.status_code in (401, 403)
