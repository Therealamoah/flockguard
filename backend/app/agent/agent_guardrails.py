"""What the agent is categorically never allowed to do, and a final
structural sanity pass over its output before anything is persisted or
shown to a farmer.

These are enforced by CONSTRUCTION, not by asking the model nicely:
prohibited actions are simply never registered in agent_tools.TOOL_SPECS,
so the model cannot call a tool that doesn't exist - there is no prompt-
level "please don't" doing the actual work. The FastAPI-level role/tenant
checks on every real write endpoint (app/core/permissions.py,
app/core/deps.py) are completely unaware of and unaffected by anything
the agent does.
"""

from __future__ import annotations

from app.agent.agent_state import AgentAssessment, Confidence, Priority

# Never exposed as callable agent tools, regardless of skill or prompt -
# documentation of intent as much as a runtime list; the real enforcement
# is that agent_tools.py's registry simply contains none of these.
PROHIBITED_ACTIONS = (
    "delete_farm",
    "delete_user",
    "remove_team_member",
    "change_user_role",
    "change_subscription",
    "change_billing",
    "change_risk_weights",
    "prescribe_medication",
    "diagnose_disease",
    "control_physical_equipment",
)

# Tool safety categories (app/agent/agent_tools.py assigns every
# registered tool exactly one of these).
READ = "read"
SAFE_WRITE = "safe_write"

# Safe-write tools create records FOR human review - they never resolve,
# assign, or notify anything by themselves.
SAFE_WRITE_TOOLS = ("create_agent_recommendation", "save_agent_brief")

# Not exposed as autonomous agent tools in this MVP at all - a human
# performs these through the existing, already-authorized endpoints
# (POST /alerts/{id}/resolve, POST .../inspections, etc.).
APPROVAL_REQUIRED_ACTIONS = ("resolve_alert", "assign_inspection", "send_external_notification")

# Shared by every farmer-facing AI reply (Ask FlockGuard, check
# explanations, daily brief, agent investigations) - FlockGuard's users are
# working poultry farmers, many with little formal schooling.
PLAIN_LANGUAGE_RULE = (
    "- Write in simple, everyday English that a poultry farmer uses on the farm. Short sentences. "
    "No technical or scientific words: say \"dead birds\" not \"mortality\", \"eating less feed\" not "
    "\"reduced feed consumption\", \"weak and dull\" not \"lethargic\", \"huddling together\" not "
    "\"crowding\", \"coughing or noisy breathing\" not \"respiratory distress\", \"how full the house is\" "
    "not \"stocking density\", \"fresh air\" not \"ventilation\" (you can add the word in brackets once), "
    "\"usual\" not \"baseline\".\n"
)

SAFETY_RULES_TEXT = (
    "Safety rules - always follow these:\n"
    + PLAIN_LANGUAGE_RULE
    + "- You are an early-warning decision-support assistant, not a veterinary or diagnostic tool. "
    "NEVER claim or imply a specific disease.\n"
    "- NEVER prescribe medication or a treatment dosage.\n"
    "- NEVER invent a measurement, record, or history that wasn't returned by a tool call.\n"
    "- Reference knowledge (from search_poultry_knowledge) may inform GENERAL guidance but must never "
    "replace or fabricate a missing farm measurement.\n"
    "- Clearly distinguish observed farm data, calculated signals, historical context, reference "
    "guidance, and your own inference - do not blend them into unattributed claims.\n"
    "- Recommend consulting a qualified poultry veterinarian or professional when risk is elevated or "
    "uncertainty is high.\n"
    "- You may recommend actions for a human to take; you never claim to have performed one yourself "
    "(you did not physically inspect anything, resolve anything, or treat anything)."
)


def validate_assessment(assessment: AgentAssessment) -> tuple[bool, str | None]:
    """Structural sanity pass beyond Pydantic's own type validation.
    Returns (ok, reason-if-not-ok). This cannot and does not verify
    factual accuracy - grounding the model in real tool results is what
    does that; this only catches internally-inconsistent output."""
    if not assessment.summary or not assessment.summary.strip():
        return False, "empty summary"
    if assessment.priority in (Priority.HIGH, Priority.URGENT) and not assessment.recommended_actions:
        return False, "high/urgent priority with no recommended actions"
    return True, None
