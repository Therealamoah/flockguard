import json
from datetime import datetime

import pytest

import app.api.routes.ask as ask_module
from app.services.grok_service import grok_service


class _FixedClock:
    def __init__(self, value: datetime):
        self.value = value

    def now(self, tz=None):
        return self.value if tz is None else self.value.astimezone(tz)


def _create_farm(client):
    return client.post("/farms", json={"name": "Test Farm"}).json()


async def _raise(*args, **kwargs):
    raise RuntimeError("upstream AI provider unreachable")


def _valid_assessment_json(summary="Everything looks fine today."):
    return json.dumps(
        {
            "priority": "low",
            "house_id": None,
            "summary": summary,
            "observed_data": [],
            "calculated_signals": [],
            "historical_context": [],
            "reference_guidance": [],
            "knowledge_sources": [],
            "recommended_actions": [],
            "confidence": "moderate",
            "requires_inspection": False,
            "requires_human_action": False,
        }
    )


async def _canned_completion(messages, tools=None, tool_choice=None, response_format=None, model=None):
    return {"content": _valid_assessment_json(), "tool_calls": None}


def test_ask_ai_service_unavailable_returns_friendly_error_not_a_crash(authed_client, monkeypatch):
    # /ask now runs through the agent (app/agent/flockguard_agent.py), which
    # calls chat_completion (tool-calling), not the older plain chat().
    monkeypatch.setattr(grok_service, "chat_completion", _raise)
    farm = _create_farm(authed_client)

    response = authed_client.post("/ask", json={"question": "Which house should I inspect first?", "farm_id": farm["id"]})

    assert response.status_code == 502
    assert "temporarily unavailable" in response.json()["detail"]


def test_ask_with_no_houses_or_history_does_not_crash(authed_client, monkeypatch):
    monkeypatch.setattr(grok_service, "chat_completion", _canned_completion)
    farm = _create_farm(authed_client)

    response = authed_client.post("/ask", json={"question": "Summarize my farm today.", "farm_id": farm["id"]})

    assert response.status_code == 200
    assert response.json()["answer"] == "Everything looks fine today."
    assert response.json()["assessment"]["priority"] == "low"


def test_ask_before_onboarding_is_handled_gracefully(authed_client, monkeypatch):
    monkeypatch.setattr(grok_service, "chat_completion", _raise)
    # No farm created at all yet. "hello" is deliberately not used here since
    # a bare greeting now short-circuits before the farm check - see
    # test_ask_greeting_gets_a_friendly_reply_without_calling_ai below.
    response = authed_client.post("/ask", json={"question": "What is my risk score?"})
    assert response.status_code == 200
    assert "onboarding" in response.json()["answer"].lower() or "farm" in response.json()["answer"].lower()


def test_ask_greeting_gets_a_friendly_reply_without_calling_ai(authed_client, monkeypatch):
    def _boom(*args, **kwargs):
        raise AssertionError("greetings must not trigger an agent run / AI call")

    monkeypatch.setattr(grok_service, "chat_completion", _boom)
    # No farm needed either - the greeting fast-path returns before any
    # farm lookup, same as before onboarding is even finished.
    response = authed_client.post("/ask", json={"question": "hi"})
    assert response.status_code == 200
    assert "answer" in response.json()
    assert "assessment" not in response.json()


def test_explain_unknown_check_returns_404(authed_client):
    farm = _create_farm(authed_client)
    house = authed_client.post(f"/farms/{farm['id']}/houses", json={"name": "House A"}).json()

    response = authed_client.post(
        "/ask/explain",
        json={"farm_id": farm["id"], "house_id": house["id"], "check_id": "does-not-exist"},
    )
    assert response.status_code == 404


def test_explain_unauthorized_house_is_not_found_not_leaked(authed_client):
    # A house_id that belongs to no farm the caller owns behaves exactly
    # like "not found" - the tenant-scoped Firestore path never resolves.
    response = authed_client.post(
        "/ask/explain",
        json={"farm_id": "someone-elses-farm", "house_id": "someone-elses-house", "check_id": "c1"},
    )
    assert response.status_code == 404


def test_daily_brief_without_ai_is_always_available(authed_client, monkeypatch):
    monkeypatch.setattr(grok_service, "chat", _raise)
    farm = _create_farm(authed_client)

    deterministic = authed_client.get(f"/farms/{farm['id']}/daily-brief")
    assert deterministic.status_code == 200
    assert deterministic.json()["available"] is True
    assert "brief_text" in deterministic.json()

    reworded = authed_client.get("/ask/daily-brief", params={"farm_id": farm["id"], "reword": True})
    assert reworded.status_code == 200
    body = reworded.json()
    assert body["available"] is True
    assert body["ai_text"] is None  # Grok failed, but the endpoint itself didn't
    assert body["brief_text"]  # deterministic text is still present


def test_daily_brief_greeting_matches_the_farms_actual_local_time(authed_client, monkeypatch):
    """Regression test: the reword prompt used to hard-code 'good morning'
    regardless of what time it actually was for the farm. It must instead
    greet correctly for the farm's own local time (UTC when no timezone is
    set), the same morning/afternoon/evening bands the frontend uses."""
    captured_messages = {}

    async def _capture_chat(messages):
        captured_messages["value"] = messages
        return "ok"

    monkeypatch.setattr(grok_service, "chat", _capture_chat)
    monkeypatch.setattr(ask_module, "datetime", _FixedClock(datetime.fromisoformat("2026-06-15T20:00:00+00:00")))
    farm = _create_farm(authed_client)

    response = authed_client.get("/ask/daily-brief", params={"farm_id": farm["id"], "reword": True})
    assert response.status_code == 200

    prompt_text = captured_messages["value"][1]["content"]
    assert "'good evening' style" in prompt_text
    assert "'good morning' style" not in prompt_text


def test_daily_brief_greeting_is_morning_when_it_actually_is(authed_client, monkeypatch):
    captured_messages = {}

    async def _capture_chat(messages):
        captured_messages["value"] = messages
        return "ok"

    monkeypatch.setattr(grok_service, "chat", _capture_chat)
    monkeypatch.setattr(ask_module, "datetime", _FixedClock(datetime.fromisoformat("2026-06-15T07:00:00+00:00")))
    farm = _create_farm(authed_client)

    response = authed_client.get("/ask/daily-brief", params={"farm_id": farm["id"], "reword": True})
    assert response.status_code == 200

    prompt_text = captured_messages["value"][1]["content"]
    assert "'good morning' style" in prompt_text
