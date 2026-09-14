import json

from app.agent.event_handlers import investigate_flock_check
from app.core.refs import agent_recommendations_ref, agent_runs_ref
from app.services.grok_service import grok_service


def _valid_assessment_json(**overrides):
    base = {
        "priority": "high",
        "house_id": "house-a",
        "summary": "House A mortality rose sharply since the morning check.",
        "observed_data": ["Mortality 2 -> 20"],
        "calculated_signals": ["Risk increased by 60 points"],
        "historical_context": [],
        "reference_guidance": [],
        "knowledge_sources": [],
        "recommended_actions": ["Check water lines", "Isolate affected birds"],
        "confidence": "moderate",
        "requires_inspection": True,
        "requires_human_action": True,
    }
    base.update(overrides)
    return json.dumps(base)


def _scripted_chat_completion(content):
    async def _fn(messages, tools=None, tool_choice=None, response_format=None, model=None):
        return {"content": content, "tool_calls": None}

    return _fn


async def test_investigate_flock_check_persists_run_and_recommendation(fake_db, monkeypatch):
    monkeypatch.setattr(grok_service, "chat_completion", _scripted_chat_completion(_valid_assessment_json()))

    await investigate_flock_check(
        fake_db,
        org_id="org-1",
        farm_id="farm-1",
        house_id="house-a",
        flock_id="flock-1",
        check_id="check-1",
        trigger="evening_check_submitted",
    )

    runs = list(agent_runs_ref(fake_db, "org-1").stream())
    assert len(runs) == 1
    assert runs[0].to_dict()["source_event_id"] == "check-1"
    assert runs[0].to_dict()["status"] == "completed"

    recommendations = list(agent_recommendations_ref(fake_db, "org-1").stream())
    assert len(recommendations) == 1
    assert recommendations[0].to_dict()["priority"] == "high"
    assert recommendations[0].to_dict()["farm_id"] == "farm-1"


async def test_investigate_flock_check_is_idempotent_per_source_event(fake_db, monkeypatch):
    call_count = {"n": 0}

    async def _fn(messages, tools=None, tool_choice=None, response_format=None, model=None):
        call_count["n"] += 1
        return {"content": _valid_assessment_json(), "tool_calls": None}

    monkeypatch.setattr(grok_service, "chat_completion", _fn)

    for _ in range(3):
        await investigate_flock_check(
            fake_db,
            org_id="org-1",
            farm_id="farm-1",
            house_id="house-a",
            flock_id=None,
            check_id="check-1",  # same source_event_id every time
            trigger="evening_check_submitted",
        )

    assert call_count["n"] == 1  # only the first call actually ran the agent
    assert len(list(agent_runs_ref(fake_db, "org-1").stream())) == 1
    assert len(list(agent_recommendations_ref(fake_db, "org-1").stream())) == 1


async def test_investigate_flock_check_low_priority_does_not_create_recommendation(fake_db, monkeypatch):
    low_priority = _valid_assessment_json(priority="low", requires_inspection=False, requires_human_action=False, recommended_actions=[])
    monkeypatch.setattr(grok_service, "chat_completion", _scripted_chat_completion(low_priority))

    await investigate_flock_check(
        fake_db, org_id="org-1", farm_id="farm-1", house_id="house-a", flock_id=None, check_id="check-1", trigger="evening_check_submitted"
    )

    assert len(list(agent_runs_ref(fake_db, "org-1").stream())) == 1
    assert list(agent_recommendations_ref(fake_db, "org-1").stream()) == []  # only high/urgent create a recommendation


async def test_investigate_flock_check_ai_failure_does_not_raise(fake_db, monkeypatch):
    async def _boom(*args, **kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr(grok_service, "chat_completion", _boom)

    # Must not raise - a background task failure should never propagate.
    await investigate_flock_check(
        fake_db, org_id="org-1", farm_id="farm-1", house_id="house-a", flock_id=None, check_id="check-1", trigger="evening_check_submitted"
    )

    runs = list(agent_runs_ref(fake_db, "org-1").stream())
    assert len(runs) == 1
    assert runs[0].to_dict()["status"] == "failed"
    assert list(agent_recommendations_ref(fake_db, "org-1").stream()) == []
