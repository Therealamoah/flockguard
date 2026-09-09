import pytest

from app.services.grok_service import grok_service


def _create_farm(client):
    return client.post("/farms", json={"name": "Test Farm"}).json()


async def _raise(*args, **kwargs):
    raise RuntimeError("upstream AI provider unreachable")


async def _canned_answer(*args, **kwargs):
    return "Everything looks fine today."


def test_ask_ai_service_unavailable_returns_friendly_error_not_a_crash(authed_client, monkeypatch):
    monkeypatch.setattr(grok_service, "chat", _raise)
    farm = _create_farm(authed_client)

    response = authed_client.post("/ask", json={"question": "Which house should I inspect first?", "farm_id": farm["id"]})

    assert response.status_code == 502
    assert "temporarily unavailable" in response.json()["detail"]


def test_ask_with_no_houses_or_history_does_not_crash(authed_client, monkeypatch):
    monkeypatch.setattr(grok_service, "chat", _canned_answer)
    farm = _create_farm(authed_client)

    response = authed_client.post("/ask", json={"question": "Summarize my farm today.", "farm_id": farm["id"]})

    assert response.status_code == 200
    assert response.json()["answer"] == "Everything looks fine today."


def test_ask_before_onboarding_is_handled_gracefully(authed_client, monkeypatch):
    monkeypatch.setattr(grok_service, "chat", _raise)
    # No farm created at all yet.
    response = authed_client.post("/ask", json={"question": "hello"})
    assert response.status_code == 200
    assert "onboarding" in response.json()["answer"].lower() or "farm" in response.json()["answer"].lower()


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
