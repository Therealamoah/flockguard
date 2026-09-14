"""Deterministic event gating and skill selection.

Running a full agent investigation costs latency and real money - this
module decides, in plain Python (no AI call involved), WHETHER an event
is worth investigating at all, and WHICH skill applies, before any Grok
request happens.
"""

from __future__ import annotations

SIGNIFICANT_RISK_CHANGE = 15  # points

INVESTIGATE_STATUSES = {"warning", "critical"}


def should_investigate_check(*, risk_status: str, risk_change: int | None, has_active_alert: bool) -> bool:
    """Gate for the *_check_submitted triggers.

    A Normal check with no meaningful change and no active alert is
    common and cheap - it's still saved, scored by the deterministic Risk
    Engine, and alert-synced exactly as before; only the (expensive,
    optional) AI investigation layer is skipped for it.
    """
    if risk_status in INVESTIGATE_STATUSES:
        return True
    if risk_status == "watch" and (risk_change or 0) >= SIGNIFICANT_RISK_CHANGE:
        return True
    if has_active_alert and (risk_change or 0) > 0:
        return True
    return False


_TRIGGER_SKILLS = {
    "morning_check_submitted": "investigate_flock_risk",
    "evening_check_submitted": "investigate_flock_risk",
    "emergency_check_submitted": "investigate_flock_risk",
    "warning_created": "investigate_flock_risk",
    "critical_alert_created": "investigate_flock_risk",
    "inspection_completed": "flock_monitoring",
    "daily_brief_requested": "daily_farm_brief",
    "unresolved_priority_followup": "farm_priority",
}


def select_skill_for_trigger(trigger: str) -> str:
    return _TRIGGER_SKILLS.get(trigger, "flock_monitoring")


_PRIORITY_WORDS = ("inspect first", "priority", "which house", "attention first", "should i inspect")
_BRIEF_WORDS = ("summarize", "summary", "brief", "overview")
_INVESTIGATE_WORDS = ("why", "flagged", "critical", "warning", "wrong")

# Presence of any of these is what distinguishes "tell me about my flock"
# from "tell me about poultry in general" - the fallback below routes to
# one skill or the other based on this, rather than defaulting every
# unmatched question to a farm investigation it has no real farm angle on.
_FARM_CONTEXT_WORDS = (
    "house", "farm", "flock", "today", "yesterday", "this week", "check",
    "alert", "mortality", "my birds", "our birds", "trend", "inspection", "radar",
)

# Greetings/pleasantries get a fast, free reply with no agent run at all -
# consistent with this module's job of deciding what's worth an AI call
# before making one (see should_investigate_check above).
_GREETING_WORDS = (
    "hi", "hello", "hey", "yo", "sup", "good morning", "good afternoon",
    "good evening", "thanks", "thank you", "how are you", "what's up",
)


def is_greeting(question: str) -> bool:
    q = (question or "").strip().lower().rstrip("!.?, ")
    if not q:
        return False
    if q in _GREETING_WORDS:
        return True
    # Only match a short leading greeting, not a real question that
    # happens to open politely, e.g. "hi, why is house A critical?".
    return len(q.split()) <= 3 and any(q.startswith(w) for w in _GREETING_WORDS)


def select_skill_for_question(question: str) -> str:
    """Keyword-based routing for Ask FlockGuard's free-text questions -
    intentionally simple; the agent's own tool selection inside a skill
    does the real investigative work. This only picks which playbook to
    load, the same way a human dispatcher would route a question to the
    right specialist rather than doing the specialism themselves."""
    q = (question or "").lower()
    if any(w in q for w in _PRIORITY_WORDS):
        return "farm_priority"
    if any(w in q for w in _BRIEF_WORDS) and "house" not in q:
        return "daily_farm_brief"
    if any(w in q for w in _INVESTIGATE_WORDS):
        return "investigate_flock_risk"
    if any(w in q for w in _FARM_CONTEXT_WORDS):
        return "flock_monitoring"
    # Not about this farmer's own data - general poultry knowledge, a
    # greeting that slipped past is_greeting, or off-topic (that skill's
    # own instructions handle refusing off-topic questions).
    return "general_poultry_knowledge"
