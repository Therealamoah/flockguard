"""The FlockGuard Agent - a bounded, custom Python tool-calling loop.

## Why a custom loop instead of LangGraph

The agent's job in this MVP is one bounded investigation per run: load a
skill, let the model request a handful of read/safe-write tool calls,
then produce one validated structured assessment. There's no multi-day
workflow, no branching between independently-resumable stages, and no
human-in-the-loop pause-and-resume *within* a single run - approval-
required actions (resolving an alert, assigning an inspection) happen
entirely OUTSIDE the agent, through the existing authenticated endpoints
(see app/core/permissions.py; app/agent/agent_guardrails.py). A `while`
loop with a max-iteration bound and Pydantic-validated final output
covers all of that. LangGraph exists for long-running, resumable,
multi-actor graphs with persisted checkpoints - none of which this app
has yet. Adding it now would mean a second execution model, a new
dependency, and new failure modes for zero of its actual benefits. If a
future skill genuinely needs multi-step state that outlives a single
request (e.g. a multi-day follow-up campaign), that's the point to
reconsider this decision - not before.

## Loop

1. Build the skill's system prompt (agent_prompts.py) + tool schemas for
   the caller's org (agent_tools.py).
2. Send the conversation to Grok with `tools` attached.
3. If the model requests tool calls, execute each through the controlled
   registry, append results as tool messages, record them on
   `AgentState`, and loop (bounded by MAX_TOOL_ITERATIONS).
4. Once the model responds with content instead of more tool calls (or
   the iteration bound is hit), parse it as JSON and validate against
   `AgentAssessment`. If invalid, retry ONCE with an explicit correction
   instruction. If still invalid, the run fails gracefully - never
   persisted, never returned as if it were valid.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from google.cloud.firestore import Client

from app.agent.agent_guardrails import validate_assessment
from app.agent.agent_prompts import build_system_prompt
from app.agent.agent_state import AgentAssessment, AgentState, ToolCallRecord
from app.agent.agent_tools import Tool, build_tool_registry, tool_schemas
from app.services.billing_service import get_subscription
from app.services.grok_service import ToolCallValidationError, grok_service
from app.services.usage_service import get_ai_requests_this_month, increment_ai_requests

_logger = logging.getLogger(__name__)

MAX_TOOL_ITERATIONS = 6


def _execute_tool_call(registry: dict[str, Tool], name: str, arguments: dict) -> str:
    tool = registry.get(name)
    if tool is None:
        return json.dumps({"error": f"Unknown tool: {name}"})
    try:
        result = tool.fn(**arguments)
    except TypeError as exc:
        return json.dumps({"error": f"Invalid arguments for {name}: {exc}"})
    except Exception:  # noqa: BLE001 - a single failing tool must not crash the whole investigation
        _logger.exception("Tool %s failed", name)
        return json.dumps({"error": f"{name} failed - data unavailable"})
    return json.dumps(result, default=str)


def _try_parse_assessment(content: str | None) -> AgentAssessment | None:
    if not content:
        return None
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    try:
        return AgentAssessment.model_validate(data)
    except Exception:  # noqa: BLE001 - any pydantic validation failure = "invalid output", handled uniformly
        return None


async def run_agent(
    db: Client,
    *,
    org_id: str,
    trigger: str,
    skill: str,
    farm_id: str | None = None,
    house_id: str | None = None,
    flock_id: str | None = None,
    source_event_id: str | None = None,
    question: str | None = None,
    extra_context: dict | None = None,
) -> AgentState:
    """Never raises - an AI/tool failure always comes back as a
    `status="failed"` AgentState, not an exception, so callers (event
    triggers, Ask FlockGuard) can degrade gracefully instead of crashing."""
    state = AgentState(
        trigger=trigger,
        org_id=org_id,
        farm_id=farm_id,
        house_id=house_id,
        flock_id=flock_id,
        source_event_id=source_event_id,
        skill=skill,
        question=question,
        model=None,
    )

    subscription = get_subscription(db, org_id)
    plan = subscription.get("plan", "pilot")
    ai_limit = subscription.get("limits", {}).get("ai_requests_monthly")
    if ai_limit is not None and get_ai_requests_this_month(db, org_id) >= ai_limit:
        state.status = "failed"
        state.error_summary = f"Monthly AI request limit ({ai_limit}) reached for the {plan.upper()} plan."
        state.completed_at = datetime.now(timezone.utc).isoformat()
        return state
    increment_ai_requests(db, org_id)

    try:
        registry = build_tool_registry(db, org_id)
        messages = _initial_messages(skill, farm_id, house_id, question, extra_context)
        assessment = await _run_loop(registry, messages, state)
        if assessment is None:
            state.status = "failed"
            state.error_summary = "AI unavailable or produced no valid assessment after retry"
        else:
            state.assessment = assessment
            state.status = "completed"
    except Exception as exc:  # noqa: BLE001 - see docstring
        _logger.exception("Agent run %s failed", state.run_id)
        state.status = "failed"
        state.error_summary = str(exc)[:300]

    state.completed_at = datetime.now(timezone.utc).isoformat()
    return state


def _initial_messages(
    skill: str, farm_id: str | None, house_id: str | None, question: str | None, extra_context: dict | None
) -> list[dict]:
    parts = []
    if farm_id:
        parts.append(f"farm_id: {farm_id}")
    if house_id:
        parts.append(f"house_id: {house_id}")
    if extra_context:
        parts.append(json.dumps(extra_context, default=str))
    parts.append(question or "Investigate and produce your assessment.")
    return [
        {"role": "system", "content": build_system_prompt(skill)},
        {"role": "user", "content": "\n".join(parts)},
    ]


async def _run_loop(registry: dict[str, Tool], messages: list[dict], state: AgentState) -> AgentAssessment | None:
    schemas = tool_schemas(registry)

    for _ in range(MAX_TOOL_ITERATIONS):
        try:
            message = await grok_service.chat_completion(messages, tools=schemas, tool_choice="auto")
        except ToolCallValidationError as exc:
            # The provider rejected the tool call before returning any message,
            # so there's no assistant/tool turn to append - just tell the model
            # what was wrong and let it retry within the same iteration budget.
            _logger.info("Agent run %s: tool call rejected (%s), asking model to retry", state.run_id, exc.detail)
            messages.append(
                {
                    "role": "user",
                    "content": (
                        f"Your last tool call was rejected: {exc.detail}. "
                        "Retry it, including every required property from its schema."
                    ),
                }
            )
            continue
        tool_calls = message.get("tool_calls") or []

        if not tool_calls:
            return await _finalize(message.get("content"), messages, state)

        messages.append({"role": "assistant", "content": message.get("content"), "tool_calls": tool_calls})
        for call in tool_calls:
            fn = call.get("function", {})
            name = fn.get("name", "")
            try:
                arguments = json.loads(fn.get("arguments") or "{}")
            except json.JSONDecodeError:
                arguments = {}
            state.tools_called.append(ToolCallRecord(tool=name, arguments=arguments))
            if name == "search_poultry_knowledge":
                state.rag_queries.append(str(arguments.get("query", "")))
            result_text = _execute_tool_call(registry, name, arguments)
            messages.append(
                {"role": "tool", "tool_call_id": call.get("id", ""), "name": name, "content": result_text}
            )

    # Ran out of iterations - force a final answer with no more tools offered.
    # Still allow one corrective retry here (not zero): live testing showed
    # this exhausted-iterations path failing outright as often as the normal
    # path when the forced answer came back malformed, for the same
    # transient-model-output reason - there's no reason to treat it less
    # forgivingly just because it arrived via the iteration cap.
    _logger.info("Agent run %s: ran out of tool iterations (%d), forcing a final answer", state.run_id, MAX_TOOL_ITERATIONS)
    content = await _force_final_answer(messages, state)
    return await _finalize(content, messages, state, max_retries=1)


async def _force_final_answer(messages: list[dict], state: AgentState) -> str | None:
    """Calls with tool_choice="none" to get plain content back. Groq's model
    sometimes tries to call a tool anyway even when none are offered, which
    Groq rejects server-side as a 400 (ToolCallValidationError) instead of
    just returning text - unlike OpenRouter/OpenAI. Make the instruction
    explicit and allow one retry before giving up on this attempt."""
    stop_tools_message = {
        "role": "user",
        "content": "Do not call any tools. Respond now with ONLY the final JSON assessment.",
    }
    messages.append(stop_tools_message)
    for attempt in range(2):
        try:
            message = await grok_service.chat_completion(messages, tool_choice="none")
            return message.get("content")
        except ToolCallValidationError as exc:
            _logger.info(
                "Agent run %s: final-answer attempt %d rejected (%s)", state.run_id, attempt, exc.detail
            )
            if attempt == 0:
                messages.append(
                    {
                        "role": "user",
                        "content": f"That was rejected: {exc.detail}. Do not call any tools - reply with plain JSON text only.",
                    }
                )
    return None


async def _finalize(
    content: str | None, messages: list[dict], state: AgentState, *, max_retries: int = 2
) -> AgentAssessment | None:
    """Validates the model's final content as an AgentAssessment, retrying up
    to `max_retries` times on malformed output before giving up. Widened from
    a single retry after live testing showed Groq's output_parse_failed /
    schema-invalid-JSON failures often succeed on a second or third corrective
    attempt within the same request - one retry alone left a meaningful share
    of otherwise-ordinary questions failing outright with a 502."""
    assessment = _try_parse_assessment(content)
    ok, reason = (False, "unparseable") if assessment is None else validate_assessment(assessment)

    attempt = 0
    while not ok and attempt < max_retries:
        attempt += 1
        _logger.info(
            "Agent run %s: retrying malformed assessment (%s), attempt %d/%d",
            state.run_id, reason, attempt, max_retries,
        )
        messages.append({"role": "assistant", "content": content})
        messages.append(
            {
                "role": "user",
                "content": (
                    "That wasn't a valid JSON assessment "
                    f"({'a required field was missing/invalid' if assessment else 'it was not valid JSON'}). "
                    "Respond again with ONLY the JSON object described earlier, nothing else."
                ),
            }
        )
        content = await _force_final_answer(messages, state)
        assessment = _try_parse_assessment(content)
        ok, reason = (False, "unparseable") if assessment is None else validate_assessment(assessment)

    if not ok or assessment is None:
        if assessment is not None:
            _logger.warning(
                "Agent run %s: assessment failed validation after %d retries (%s)",
                state.run_id, attempt, reason,
            )
        return None

    state.rag_sources_used = assessment.knowledge_sources
    return assessment
