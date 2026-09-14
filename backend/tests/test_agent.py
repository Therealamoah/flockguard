import json

import pytest

from app.agent.agent_guardrails import validate_assessment
from app.agent.agent_prompts import build_system_prompt
from app.agent.agent_router import is_greeting, select_skill_for_question, select_skill_for_trigger, should_investigate_check
from app.agent.agent_state import AgentAssessment, Confidence, Priority
from app.agent.agent_tools import build_tool_registry
from app.agent.flockguard_agent import run_agent
from app.agent.skill_loader import SKILL_REGISTRY, UnknownSkillError, available_skills, load_skill
from app.core.refs import agent_recommendations_ref, agent_runs_ref, flocks_ref, houses_ref, subscription_ref
from app.services.grok_service import grok_service
from app.services.usage_service import current_period_key, get_ai_requests_this_month, usage_periods_ref

ORG = "org-1"
FARM = "farm-1"


def _scripted_chat_completion(responses):
    calls = {"n": 0}

    async def _fn(messages, tools=None, tool_choice=None, response_format=None, model=None):
        if calls["n"] >= len(responses):
            raise AssertionError("chat_completion called more times than scripted")
        response = responses[calls["n"]]
        calls["n"] += 1
        return response

    _fn.call_count = lambda: calls["n"]
    return _fn


def _valid_assessment_json(**overrides):
    base = {
        "priority": "medium",
        "house_id": "house-a",
        "summary": "House A mortality rose modestly since the morning check.",
        "observed_data": ["Mortality 2 -> 5"],
        "calculated_signals": ["Risk increased by 20 points"],
        "historical_context": [],
        "reference_guidance": [],
        "knowledge_sources": [],
        "recommended_actions": ["Check water lines"],
        "confidence": "moderate",
        "requires_inspection": True,
        "requires_human_action": True,
    }
    base.update(overrides)
    return json.dumps(base)


# ---------------------------------------------------------------------------
# Skill loader
# ---------------------------------------------------------------------------


def test_all_skills_registered_and_loadable():
    assert available_skills() == sorted(
        [
            "flock_monitoring",
            "investigate_flock_risk",
            "inspection_planning",
            "daily_farm_brief",
            "farm_priority",
            "poultry_safety",
            "general_poultry_knowledge",
        ]
    )
    for name in available_skills():
        content = load_skill(name)
        assert len(content) > 50


def test_unknown_skill_rejected():
    with pytest.raises(UnknownSkillError):
        load_skill("not_a_real_skill")


def test_path_traversal_impossible():
    for attempt in ("../../secret", "/etc/passwd", "..\\..\\windows", "poultry_safety/../../../etc/passwd"):
        with pytest.raises(UnknownSkillError):
            load_skill(attempt)
    # And the registry itself only ever contains fixed, known paths.
    assert all(str(path).endswith("SKILL.md") for path in SKILL_REGISTRY.values())


# ---------------------------------------------------------------------------
# Deterministic gating and routing
# ---------------------------------------------------------------------------


def test_gating_normal_check_does_not_trigger_investigation():
    assert should_investigate_check(risk_status="normal", risk_change=0, has_active_alert=False) is False


def test_gating_warning_and_critical_always_trigger():
    assert should_investigate_check(risk_status="warning", risk_change=1, has_active_alert=False) is True
    assert should_investigate_check(risk_status="critical", risk_change=0, has_active_alert=False) is True


def test_gating_watch_with_small_change_and_no_alert_does_not_trigger():
    assert should_investigate_check(risk_status="watch", risk_change=3, has_active_alert=False) is False


def test_gating_watch_with_large_change_triggers():
    assert should_investigate_check(risk_status="watch", risk_change=20, has_active_alert=False) is True


def test_skill_selection_for_triggers():
    assert select_skill_for_trigger("critical_alert_created") == "investigate_flock_risk"
    assert select_skill_for_trigger("daily_brief_requested") == "daily_farm_brief"
    assert select_skill_for_trigger("unresolved_priority_followup") == "farm_priority"
    assert select_skill_for_trigger("something_unknown") == "flock_monitoring"


def test_skill_selection_for_questions():
    assert select_skill_for_question("Which house should I inspect first?") == "farm_priority"
    assert select_skill_for_question("Summarize my farm today") == "daily_farm_brief"
    assert select_skill_for_question("Why is House C critical?") == "investigate_flock_risk"
    assert select_skill_for_question("What happened to House A?") == "flock_monitoring"


def test_skill_selection_falls_back_to_general_knowledge_for_non_farm_questions():
    assert select_skill_for_question("What's the ideal brooding temperature for day-old chicks?") == "general_poultry_knowledge"
    assert select_skill_for_question("What feed conversion ratio should I expect from Ross 308 broilers?") == "general_poultry_knowledge"
    # "house" makes this farm-specific even without an explicit "my" - the
    # keyword heuristic is intentionally simple, not perfect NLP.
    assert select_skill_for_question("How do I control ammonia buildup in a broiler house?") == "flock_monitoring"


def test_is_greeting_matches_short_pleasantries_only():
    assert is_greeting("hi") is True
    assert is_greeting("Hello!") is True
    assert is_greeting("thanks") is True
    assert is_greeting("hi, why is house A critical?") is False  # a real question, not just a greeting
    assert is_greeting("What happened to House A?") is False
    assert is_greeting("") is False


def test_build_system_prompt_merges_poultry_safety_baseline_for_other_skills():
    prompt = build_system_prompt("general_poultry_knowledge")
    assert "Baseline: poultry_safety" in prompt
    assert "Never prescribe medication" in prompt  # from poultry_safety SKILL.md
    assert "Active skill: general_poultry_knowledge" in prompt


def test_build_system_prompt_does_not_duplicate_poultry_safety_when_active():
    prompt = build_system_prompt("poultry_safety")
    assert prompt.count("Never prescribe medication") == 1


# ---------------------------------------------------------------------------
# Guardrails
# ---------------------------------------------------------------------------


def test_validate_assessment_rejects_high_priority_with_no_actions():
    assessment = AgentAssessment(priority=Priority.HIGH, summary="Something is wrong.", confidence=Confidence.HIGH)
    ok, reason = validate_assessment(assessment)
    assert ok is False
    assert "recommended actions" in reason


def test_validate_assessment_accepts_low_priority_with_no_actions():
    assessment = AgentAssessment(priority=Priority.LOW, summary="All stable.", confidence=Confidence.HIGH)
    ok, _ = validate_assessment(assessment)
    assert ok is True


def test_validate_assessment_rejects_empty_summary():
    assessment = AgentAssessment(priority=Priority.LOW, summary="   ", confidence=Confidence.LOW)
    ok, reason = validate_assessment(assessment)
    assert ok is False
    assert "summary" in reason


# ---------------------------------------------------------------------------
# Tool registry - tenant isolation and graceful missing data
# ---------------------------------------------------------------------------


def test_tool_registry_missing_farm_returns_available_false_not_crash(fake_db):
    registry = build_tool_registry(fake_db, ORG)
    result = registry["get_farm_status"].fn(farm_id="does-not-exist")
    assert result == {"available": False}


def test_tool_registry_missing_house_returns_available_false(fake_db):
    houses_ref(fake_db, ORG, FARM)  # no houses created
    registry = build_tool_registry(fake_db, ORG)
    result = registry["get_house_status"].fn(farm_id=FARM, house_id="ghost-house")
    assert result == {"available": False}


def test_tool_registry_is_isolated_per_org(fake_db):
    houses_ref(fake_db, ORG, FARM).document("house-a").set({"name": "House A"})
    houses_ref(fake_db, "org-2", FARM).document("house-b").set({"name": "Someone Else's House"})

    registry_a = build_tool_registry(fake_db, ORG)
    comparison = registry_a["get_house_comparison"].fn(farm_id=FARM)
    assert [h["house_id"] for h in comparison] == ["house-a"]  # never sees org-2's house


def test_tool_registry_history_limit_is_capped(fake_db):
    registry = build_tool_registry(fake_db, ORG)
    # limit=9999 must be silently capped, not passed straight through to Firestore.
    result = registry["get_flock_history"].fn(farm_id=FARM, house_id="house-a", limit=9999)
    assert result == []  # no data yet, but the call itself must not raise


def test_create_agent_recommendation_tool_writes_a_record(fake_db):
    registry = build_tool_registry(fake_db, ORG)
    result = registry["create_agent_recommendation"].fn(
        farm_id=FARM, house_id="house-a", title="Check water", summary="Water use dropped.", priority="high"
    )
    assert result["status"] == "open"
    stored = list(agent_recommendations_ref(fake_db, ORG).stream())
    assert len(stored) == 1


# ---------------------------------------------------------------------------
# The agent loop itself
# ---------------------------------------------------------------------------


async def test_agent_completes_with_no_tool_calls_needed(fake_db, monkeypatch):
    chat = _scripted_chat_completion([{"content": _valid_assessment_json(), "tool_calls": None}])
    monkeypatch.setattr(grok_service, "chat_completion", chat)

    state = await run_agent(fake_db, org_id=ORG, trigger="evening_check_submitted", skill="investigate_flock_risk", farm_id=FARM, house_id="house-a")

    assert state.status == "completed"
    assert state.assessment.priority == Priority.MEDIUM
    assert state.tools_called == []


async def test_agent_executes_requested_tool_then_finalizes(fake_db, monkeypatch):
    houses_ref(fake_db, ORG, FARM).document("house-a").set({"name": "House A"})

    tool_call = {
        "id": "call_1",
        "function": {"name": "get_house_status", "arguments": json.dumps({"farm_id": FARM, "house_id": "house-a"})},
    }
    chat = _scripted_chat_completion(
        [
            {"content": None, "tool_calls": [tool_call]},
            {"content": _valid_assessment_json(), "tool_calls": None},
        ]
    )
    monkeypatch.setattr(grok_service, "chat_completion", chat)

    state = await run_agent(fake_db, org_id=ORG, trigger="evening_check_submitted", skill="investigate_flock_risk", farm_id=FARM, house_id="house-a")

    assert state.status == "completed"
    assert [t.tool for t in state.tools_called] == ["get_house_status"]
    assert chat.call_count() == 2


async def test_agent_retries_once_on_invalid_json_then_succeeds(fake_db, monkeypatch):
    chat = _scripted_chat_completion(
        [
            {"content": "not json at all", "tool_calls": None},
            {"content": _valid_assessment_json(), "tool_calls": None},
        ]
    )
    monkeypatch.setattr(grok_service, "chat_completion", chat)

    state = await run_agent(fake_db, org_id=ORG, trigger="evening_check_submitted", skill="flock_monitoring", farm_id=FARM, house_id="house-a")

    assert state.status == "completed"
    assert chat.call_count() == 2


async def test_agent_fails_gracefully_after_two_invalid_responses(fake_db, monkeypatch):
    chat = _scripted_chat_completion(
        [
            {"content": "garbage", "tool_calls": None},
            {"content": "still garbage", "tool_calls": None},
        ]
    )
    monkeypatch.setattr(grok_service, "chat_completion", chat)

    state = await run_agent(fake_db, org_id=ORG, trigger="evening_check_submitted", skill="flock_monitoring", farm_id=FARM, house_id="house-a")

    assert state.status == "failed"
    assert state.error_summary is not None
    assert state.assessment is None


async def test_agent_handles_ai_provider_failure_without_raising(fake_db, monkeypatch):
    async def _boom(*args, **kwargs):
        raise RuntimeError("upstream unreachable")

    monkeypatch.setattr(grok_service, "chat_completion", _boom)

    state = await run_agent(fake_db, org_id=ORG, trigger="evening_check_submitted", skill="flock_monitoring", farm_id=FARM, house_id="house-a")

    assert state.status == "failed"
    assert "unreachable" in state.error_summary


async def test_agent_run_persists_no_chain_of_thought_only_summaries(fake_db, monkeypatch):
    chat = _scripted_chat_completion([{"content": _valid_assessment_json(), "tool_calls": None}])
    monkeypatch.setattr(grok_service, "chat_completion", chat)

    state = await run_agent(fake_db, org_id=ORG, trigger="evening_check_submitted", skill="investigate_flock_risk", farm_id=FARM, house_id="house-a")
    doc = state.to_run_document()

    assert "reasoning" not in json.dumps(doc)  # no raw model reasoning field at all
    assert doc["evidence_summary"] == state.assessment.summary
    assert doc["priority"] == "medium"


async def test_agent_run_increments_the_orgs_monthly_ai_request_count(fake_db, monkeypatch):
    chat = _scripted_chat_completion([{"content": _valid_assessment_json(), "tool_calls": None}])
    monkeypatch.setattr(grok_service, "chat_completion", chat)

    assert get_ai_requests_this_month(fake_db, ORG) == 0
    await run_agent(fake_db, org_id=ORG, trigger="evening_check_submitted", skill="investigate_flock_risk", farm_id=FARM, house_id="house-a")
    assert get_ai_requests_this_month(fake_db, ORG) == 1


async def test_agent_run_blocked_once_monthly_ai_quota_is_reached(fake_db, monkeypatch):
    # Any call to grok_service here would fail the test (see conftest's
    # _no_real_ai_calls_by_default) - proving run_agent short-circuits
    # BEFORE spending an API call once the plan's quota is already used up.
    subscription_ref(fake_db, ORG).set({"limits": {"ai_requests_monthly": 5}}, merge=True)
    usage_periods_ref(fake_db, ORG).document(current_period_key()).set({"ai_requests": 5})

    state = await run_agent(fake_db, org_id=ORG, trigger="evening_check_submitted", skill="investigate_flock_risk", farm_id=FARM, house_id="house-a")

    assert state.status == "failed"
    assert "AI request limit" in state.error_summary
    assert get_ai_requests_this_month(fake_db, ORG) == 5  # unchanged - no call was made or counted
