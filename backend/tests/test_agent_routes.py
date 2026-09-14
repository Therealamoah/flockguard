from app.agent.event_handlers import investigate_flock_check
from app.services.grok_service import grok_service
import json


def _valid_assessment_json(priority="high"):
    return json.dumps(
        {
            "priority": priority,
            "house_id": "house-a",
            "summary": "House A needs attention.",
            "observed_data": [],
            "calculated_signals": [],
            "historical_context": [],
            "reference_guidance": [],
            "knowledge_sources": [],
            "recommended_actions": ["Inspect water lines"],
            "confidence": "moderate",
            "requires_inspection": True,
            "requires_human_action": True,
        }
    )


async def test_list_recommendations_requires_auth(client):
    response = client.get("/agent/recommendations")
    assert response.status_code == 401


async def _seed_recommendation(fake_db, org_id, monkeypatch, priority="high"):
    async def _fn(messages, tools=None, tool_choice=None, response_format=None, model=None):
        return {"content": _valid_assessment_json(priority), "tool_calls": None}

    monkeypatch.setattr(grok_service, "chat_completion", _fn)
    await investigate_flock_check(
        fake_db, org_id=org_id, farm_id="farm-1", house_id="house-a", flock_id=None, check_id="check-1",
        trigger="evening_check_submitted",
    )


async def test_owner_can_list_and_act_on_recommendations(authed_client, fake_db, monkeypatch):
    from tests.conftest import FAKE_UID

    await _seed_recommendation(fake_db, FAKE_UID, monkeypatch)

    listed = authed_client.get("/agent/recommendations").json()
    assert len(listed) == 1
    rec_id = listed[0]["id"]
    assert listed[0]["status"] == "open"

    ack = authed_client.post(f"/agent/recommendations/{rec_id}/acknowledge")
    assert ack.status_code == 200
    assert ack.json()["status"] == "acknowledged"

    complete = authed_client.post(f"/agent/recommendations/{rec_id}/complete")
    assert complete.status_code == 200
    assert complete.json()["status"] == "completed"


async def test_recommendations_filter_by_house(authed_client, fake_db, monkeypatch):
    from tests.conftest import FAKE_UID

    await _seed_recommendation(fake_db, FAKE_UID, monkeypatch)

    matching = authed_client.get("/agent/recommendations", params={"house_id": "house-a"}).json()
    assert len(matching) == 1
    none_matching = authed_client.get("/agent/recommendations", params={"house_id": "house-b"}).json()
    assert none_matching == []


async def test_dismiss_unknown_recommendation_returns_404(authed_client):
    response = authed_client.post("/agent/recommendations/does-not-exist/dismiss")
    assert response.status_code == 404


async def test_agent_runs_audit_log_excludes_chain_of_thought(authed_client, fake_db, monkeypatch):
    from tests.conftest import FAKE_UID

    await _seed_recommendation(fake_db, FAKE_UID, monkeypatch)

    runs = authed_client.get("/agent/runs").json()
    assert len(runs) == 1
    assert "reasoning" not in json.dumps(runs[0])
    assert runs[0]["status"] == "completed"
    assert runs[0]["priority"] == "high"


async def test_cross_org_recommendations_isolated(make_client, monkeypatch):
    async def _fn(messages, tools=None, tool_choice=None, response_format=None, model=None):
        return {"content": _valid_assessment_json(), "tool_calls": None}

    monkeypatch.setattr(grok_service, "chat_completion", _fn)

    org_a = make_client("org-a-owner", "a@example.com")
    org_a.get("/team")  # backfill membership

    # Directly invoke against org A's data using the shared fake_db behind make_client.
    from app.core.firestore import get_firestore_client as _dep
    from app.main import app as _app

    db = _app.dependency_overrides[_dep]()
    await investigate_flock_check(
        db, org_id="org-a-owner", farm_id="farm-1", house_id="house-a", flock_id=None, check_id="check-1",
        trigger="evening_check_submitted",
    )

    org_b = make_client("org-b-owner", "b@example.com")
    assert org_b.get("/agent/recommendations").json() == []
