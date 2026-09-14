"""Builds the system prompt for a given skill run.

Every prompt = the global safety rules + the loaded skill's procedure +
a fixed instruction for how to produce the final structured output. The
skill content itself is untouched, controlled markdown (see
skill_loader.py) - this module only assembles it, never edits it.
"""

from __future__ import annotations

from app.agent.agent_guardrails import SAFETY_RULES_TEXT
from app.agent.skill_loader import load_skill

FINAL_OUTPUT_INSTRUCTION = (
    "When you have gathered enough evidence (or determined no more tools are useful), respond with your "
    "final assessment as a single JSON object matching this shape - no prose outside the JSON:\n"
    "{\n"
    '  "priority": "low" | "medium" | "high" | "urgent",\n'
    '  "house_id": string or null,\n'
    '  "summary": string (2-4 sentences),\n'
    '  "observed_data": [string, ...]  (raw facts a tool actually returned),\n'
    '  "calculated_signals": [string, ...]  (Risk Engine / trend detector output),\n'
    '  "historical_context": [string, ...]  (prior checks/inspections that inform this),\n'
    '  "reference_guidance": [string, ...]  (only if search_poultry_knowledge was used and returned something),\n'
    '  "knowledge_sources": [{"document_id", "title", "publisher", "section", "page", "source_url"}, ...] '
    "(ONLY sources actually returned by search_poultry_knowledge - never invent one),\n"
    '  "recommended_actions": [string, ...],\n'
    '  "confidence": "low" | "moderate" | "high",\n'
    '  "requires_inspection": boolean,\n'
    '  "requires_human_action": boolean\n'
    "}\n"
    "Every list should be built ONLY from what your tool calls actually returned - never invented. "
    "If evidence is thin, say so plainly and use confidence: \"low\" rather than overstating certainty."
)


def build_system_prompt(skill: str) -> str:
    skill_content = load_skill(skill)
    # poultry_safety applies to every run regardless of which skill is
    # active (see its own SKILL.md) - other skills reference it by name
    # assuming its rules are in context, so it must actually be merged in
    # here rather than only loaded when it's itself the selected skill.
    baseline = "" if skill == "poultry_safety" else f"## Baseline: poultry_safety\n\n{load_skill('poultry_safety')}\n\n"
    return (
        "You are the FlockGuard Agent, the AI decision/orchestration layer inside the FlockGuard poultry "
        "early-warning platform. You investigate using controlled tools that read FlockGuard's real farm "
        "data - you never see or query Firestore directly, and you never calculate or override a Risk "
        "Engine score yourself.\n\n"
        f"{SAFETY_RULES_TEXT}\n\n"
        f"{baseline}"
        f"## Active skill: {skill}\n\n{skill_content}\n\n"
        f"{FINAL_OUTPUT_INSTRUCTION}"
    )
