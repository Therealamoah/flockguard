import json
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from google.cloud.firestore import Client

from app.agent.agent_router import is_greeting, select_skill_for_question
from app.agent.flockguard_agent import run_agent
from app.core.config import settings
from app.core.deps import get_current_org_id
from app.core.firestore import get_firestore_client
from app.core.limiter import limiter
from app.core.refs import agent_runs_ref, farms_ref, flock_checks_ref
from app.models.schemas import AskRequest, ExplainCheckRequest
from app.services.comparison_service import build_morning_evening_comparison, resolve_timezone
from app.services.daily_brief_service import build_daily_brief
from app.services.farm_context_service import (
    get_farm_status,
    get_flock_history,
    get_house_status,
    list_houses,
    resolve_house,
)
from app.services.billing_service import get_subscription
from app.services.grok_service import grok_service
from app.services.usage_service import get_ai_requests_this_month, increment_ai_requests

_logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ask", tags=["ask-flockguard"])

# Ask FlockGuard is a decision-support assistant, not a diagnostic one. This
# is enforced at the prompt level everywhere Grok is called from this file:
# it only ever gets FlockGuard's own already-computed data (never invents
# records), and is explicitly told not to name diseases.
SAFETY_RULES = (
    "Safety rules, always follow these:\n"
    "- You are an early-warning decision-support assistant, not a veterinary or "
    "diagnostic tool. NEVER claim or imply a specific disease (e.g. do not say "
    "things like \"this is Newcastle disease\").\n"
    "- Clearly distinguish observed data (what FlockGuard recorded) from your own "
    "inference or suggestions. Phrase concerns as symptoms/records, e.g. "
    "\"records show increased mortality and reduced activity\" rather than a diagnosis.\n"
    "- Only use the data given to you below. If something is not in it, say plainly "
    "that the record isn't available - never invent farm data, numbers, or history.\n"
    "- When risk is elevated, suggest concrete next steps (inspect water, feed, "
    "ventilation, isolate affected birds) and, for Warning/Critical situations, "
    "recommend consulting a qualified poultry professional or veterinarian if "
    "concerns continue.\n"
    "- Be concise and speak plainly to a working farmer."
)

SYSTEM_PROMPT = (
    "You are Ask FlockGuard, the AI assistant inside the FlockGuard poultry "
    "early-warning platform. You explain risk scores, alerts, comparisons and "
    "trends that FlockGuard's deterministic Risk Engine and trend detector have "
    "already calculated - you never calculate or override a risk score yourself.\n\n"
    f"{SAFETY_RULES}"
)

AI_UNAVAILABLE_MESSAGE = (
    "FlockGuard AI is temporarily unavailable, so I can't answer that right now. "
    "Your farm monitoring, Risk Engine, Radar and alerts are still working normally - "
    "please try asking again shortly."
)


def _resolve_farm_id(db: Client, org_id: str, requested_farm_id: str | None) -> str | None:
    if requested_farm_id:
        return requested_farm_id
    docs = list(farms_ref(db, org_id).limit(1).stream())
    return docs[0].id if docs else None


async def _safe_chat(db: Client, org_id: str, messages: list[dict]) -> str | None:
    """Never raises. Returns None (instead of an exception) if Grok is down,
    times out, errors, or the plan's monthly AI quota is already used up -
    callers decide the graceful fallback. Used by /ask/explain and
    /ask/daily-brief below, which are narrow, single-purpose grounded
    prompts rather than open-ended investigations (those go through
    app/agent/flockguard_agent.py::run_agent, which enforces/tracks this
    same quota for itself)."""
    subscription = get_subscription(db, org_id)
    limit = subscription.get("limits", {}).get("ai_requests_monthly")
    if limit is not None and get_ai_requests_this_month(db, org_id) >= limit:
        _logger.info("Org %s hit its monthly AI request limit; skipping Grok call", org_id)
        return None
    try:
        answer = await grok_service.chat(messages)
    except Exception:  # noqa: BLE001 - any AI-layer failure must not break the caller
        _logger.exception("Grok call failed; falling back gracefully")
        return None
    increment_ai_requests(db, org_id)
    return answer


@router.post("")
@limiter.limit(settings.rate_limit_ask)
async def ask_flockguard(
    request: Request,
    payload: AskRequest,
    org_id: str = Depends(get_current_org_id),
    db: Client = Depends(get_firestore_client),
):
    """Ask FlockGuard runs on the SAME Agent + Skills + Tools architecture
    as event-triggered investigations (app/agent/) - not a second,
    independent AI system. A free-text question is routed to a skill
    (app/agent/agent_router.py::select_skill_for_question), and the agent
    decides for itself which controlled tools it needs to answer it,
    rather than this route pre-guessing and dumping a fixed context blob.
    """
    if is_greeting(payload.question):
        # No agent run for a bare greeting - cheap, instant, and consistent
        # with this file's own docstring elsewhere about not spending an AI
        # call on something plain Python can already answer.
        return {
            "answer": (
                "Hi! I'm here to help with your flocks, houses, alerts, and general poultry-care "
                "questions - what would you like to know?"
            )
        }

    farm_id = _resolve_farm_id(db, org_id, payload.farm_id)
    if not farm_id:
        return {"answer": "You don't have a farm set up yet - finish onboarding first and I'll be able to help."}

    house_id = None
    if payload.house_id:
        match = resolve_house(list_houses(db, org_id, farm_id), payload.house_id)
        house_id = match["id"] if match else None

    skill = select_skill_for_question(payload.question)
    state = await run_agent(
        db,
        org_id=org_id,
        trigger="ask_flockguard_question",
        skill=skill,
        farm_id=farm_id,
        house_id=house_id,
        question=payload.question,
    )

    # Persisted the same way an event-triggered run is - one audit trail,
    # regardless of what triggered the investigation.
    agent_runs_ref(db, org_id).document(state.run_id).set(state.to_run_document())

    if state.status != "completed" or not state.assessment:
        if state.error_summary and "AI request limit" in state.error_summary:
            raise HTTPException(status_code=402, detail=state.error_summary)
        raise HTTPException(status_code=502, detail=AI_UNAVAILABLE_MESSAGE)

    return {"answer": state.assessment.summary, "assessment": state.assessment.model_dump(mode="json")}


@router.post("/explain")
@limiter.limit(settings.rate_limit_ask)
async def explain_check(
    request: Request,
    payload: ExplainCheckRequest,
    org_id: str = Depends(get_current_org_id),
    db: Client = Depends(get_firestore_client),
):
    """Grounded 'Why is this house flagged?' explanation for one Flock Check.

    Unlike a free-text question, this always includes: the check's own risk
    factors, the previous score and computed risk_change, its Morning/Evening
    comparison (if any), and the house's currently open alert - all real
    values already computed by the Risk Engine / Alert Engine / comparison
    service, never invented by Grok.
    """
    farm_id, house_id, check_id = payload.farm_id, payload.house_id, payload.check_id
    doc = flock_checks_ref(db, org_id, farm_id, house_id).document(check_id).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Flock Check not found")
    check = {"id": doc.id, **doc.to_dict()}

    status = get_house_status(db, org_id, farm_id, house_id)
    house_name = status["house"].get("name") if status else house_id
    comparison = check.get("morning_comparison")
    if comparison is None:
        recent = get_flock_history(db, org_id, farm_id, house_id, limit=20)
        comparison = build_morning_evening_comparison(recent, check)

    explanation_context = {
        "house_name": house_name,
        "period": check.get("period"),
        "current_risk_score": check.get("risk_score"),
        "current_risk_status": check.get("risk_status"),
        "previous_risk_score": check.get("previous_risk_score"),
        "risk_change": check.get("risk_change"),
        "risk_factors": check.get("risk_factors"),
        "morning_evening_comparison": comparison,
        "active_alert": (status.get("active_alerts") or [None])[0] if status else None,
    }

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "system",
            "content": (
                "Explain, in 2-4 short sentences, why this Flock Check scored the way it did. "
                "Lead with the score change if previous_risk_score is present (e.g. '54 -> 81 (+27)'). "
                "Then name the main contributing factors, grounded only in the data below:\n"
                + json.dumps(explanation_context, default=str)
            ),
        },
        {"role": "user", "content": f"Why is {house_name} {check.get('risk_status')}?"},
    ]

    answer = await _safe_chat(db, org_id, messages)
    return {
        "available": answer is not None,
        "explanation": answer,
        "grounded_data": explanation_context,
    }


@router.get("/daily-brief")
@limiter.limit(settings.rate_limit_ask)
async def ai_daily_brief(
    request: Request,
    farm_id: str | None = None,
    reword: bool = True,
    org_id: str = Depends(get_current_org_id),
    db: Client = Depends(get_firestore_client),
):
    """Daily Brief, optionally reworded by Grok for a warmer tone.

    The structured/deterministic version (app/services/daily_brief_service.py,
    also plainly available at GET /farms/{farm_id}/daily-brief with no AI
    involved at all) is always computed first and always returned as
    `deterministic_text` - if Grok is unavailable or `reword=false`, the
    response is still complete and useful, just not restyled.
    """
    resolved_farm_id = _resolve_farm_id(db, org_id, farm_id)
    if not resolved_farm_id:
        return {"available": False, "reason": "no_farm"}

    status = get_farm_status(db, org_id, resolved_farm_id)
    if not status:
        return {"available": False, "reason": "farm_not_found"}

    brief = build_daily_brief(status)
    result = {"available": True, **brief, "ai_text": None}

    if reword:
        # Previously hard-coded a "good morning" style greeting regardless
        # of the actual time of day - fixed to greet correctly based on the
        # farm's own local time (falls back to UTC if no timezone is set,
        # same convention as comparison_service/farm_context_service),
        # matching frontend/src/lib/time.js::greetingFor's morning/
        # afternoon/evening bands exactly.
        farm_tz = resolve_timezone(status.get("farm", {}).get("timezone"))
        local_hour = datetime.now(farm_tz).hour
        greeting_word = "morning" if local_hour < 12 else "afternoon" if local_hour < 18 else "evening"

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "system",
                "content": (
                    f"Rewrite the following farm summary as a warm, brief 'good {greeting_word}' style "
                    "greeting for a farmer (3-5 short sentences, no invented facts, no diagnosis). "
                    f"It is currently {greeting_word} at this farm, so greet accordingly - never say "
                    f"'good morning' unless the greeting word above is 'morning':\n" + brief["brief_text"]
                ),
            },
            {"role": "user", "content": "Give me today's farm brief."},
        ]
        result["ai_text"] = await _safe_chat(db, org_id, messages)

    return result
