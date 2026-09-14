"""The controlled tool registry - the ONLY way the agent touches
FlockGuard data. The model never queries Firestore directly; it can only
request a named tool with JSON-serializable arguments, and this module
decides what actually runs.

Security model: `build_tool_registry(db, org_id)` is called once per
request/agent-run with `org_id` derived from the AUTHENTICATED CALLER
(never from the model or any request body - see app/core/deps.py). Every
wrapped function below closes over that `org_id`; there is no tool
parameter through which a model could supply a different one. `farm_id`/
`house_id` ARE model-supplied, but every underlying
farm_context_service/comparison_service call is already scoped under
`organizations/{org_id}/...` by construction (app/core/refs.py) - an
invalid or foreign farm_id/house_id simply resolves to "not found" data,
never another organization's data.

Tool safety categories (app/agent/agent_guardrails.py): every tool here
is READ or SAFE_WRITE. Nothing in APPROVAL_REQUIRED_ACTIONS or
PROHIBITED_ACTIONS is registered here at all.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from google.cloud.firestore import Client

from app.agent.agent_guardrails import READ, SAFE_WRITE
from app.core.refs import agent_recommendations_ref
from app.services import comparison_service
from app.services import farm_context_service as fcs
from app.services import knowledge_service
from app.services.trend_service import detect_trends

_MAX_HISTORY_LIMIT = 20


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]  # JSON schema, OpenAI tool-calling format
    category: str
    fn: Callable[..., Any]

    def to_openai_schema(self) -> dict:
        return {
            "type": "function",
            "function": {"name": self.name, "description": self.description, "parameters": self.parameters},
        }


def _house_history_params(extra: dict | None = None) -> dict:
    props = {
        "farm_id": {"type": "string"},
        "house_id": {"type": "string"},
        "limit": {"type": "integer", "description": "Max records, default 7, capped at 20"},
    }
    if extra:
        props.update(extra)
    return {"type": "object", "properties": props, "required": ["farm_id", "house_id"]}


def build_tool_registry(db: Client, org_id: str) -> dict[str, Tool]:
    """Builds a fresh registry per request, with `db`/`org_id` baked in via
    closure - see module docstring for why that's the security boundary."""

    def _cap(limit: int | None) -> int:
        return min(limit or 7, _MAX_HISTORY_LIMIT)

    def get_farm_status(farm_id: str) -> dict:
        return fcs.get_farm_status(db, org_id, farm_id) or {"available": False}

    def get_house_status(farm_id: str, house_id: str) -> dict:
        return fcs.get_house_status(db, org_id, farm_id, house_id) or {"available": False}

    def get_current_flock(farm_id: str, house_id: str) -> dict:
        return fcs.get_current_flock(db, org_id, farm_id, house_id) or {"available": False}

    def get_latest_flock_check(farm_id: str, house_id: str) -> dict:
        return fcs.get_latest_flock_check(db, org_id, farm_id, house_id) or {"available": False}

    def get_morning_check(farm_id: str, house_id: str) -> dict:
        return fcs.get_check_for_period_today(db, org_id, farm_id, house_id, "morning") or {"available": False}

    def get_evening_check(farm_id: str, house_id: str) -> dict:
        return fcs.get_check_for_period_today(db, org_id, farm_id, house_id, "evening") or {"available": False}

    def get_flock_history(farm_id: str, house_id: str, limit: int | None = None) -> list:
        return fcs.get_flock_history(db, org_id, farm_id, house_id, limit=_cap(limit))

    def get_risk_history(farm_id: str, house_id: str, limit: int | None = None) -> list:
        return fcs.get_risk_history(db, org_id, farm_id, house_id, limit=_cap(limit))

    def get_mortality_history(farm_id: str, house_id: str, limit: int | None = None) -> list:
        return fcs.get_mortality_history(db, org_id, farm_id, house_id, limit=_cap(limit))

    def get_feed_history(farm_id: str, house_id: str, limit: int | None = None) -> list:
        return fcs.get_feed_history(db, org_id, farm_id, house_id, limit=_cap(limit))

    def get_water_history(farm_id: str, house_id: str, limit: int | None = None) -> list:
        return fcs.get_water_history(db, org_id, farm_id, house_id, limit=_cap(limit))

    def get_active_alerts(farm_id: str | None = None, house_id: str | None = None) -> list:
        return fcs.get_active_alerts(db, org_id, farm_id, house_id)

    def get_recent_inspections(farm_id: str, house_id: str, limit: int | None = None) -> list:
        return fcs.get_recent_inspections(db, org_id, farm_id, house_id, limit=min(limit or 5, 10))

    def get_house_comparison(farm_id: str) -> list:
        return fcs.get_house_comparison(db, org_id, farm_id)

    def get_trend_insights(farm_id: str, house_id: str) -> list:
        history = fcs.get_flock_history(db, org_id, farm_id, house_id, limit=3)
        houses = fcs.list_houses(db, org_id, farm_id)
        house_name = next((h.get("name") for h in houses if h["id"] == house_id), house_id)
        return detect_trends(house_id, house_name, history)

    def get_previous_similar_inspections(
        farm_id: str, house_id: str, finding_category: str | None = None, limit: int | None = None
    ) -> list:
        return fcs.get_previous_similar_inspections(
            db, org_id, farm_id, house_id, finding_category, limit=min(limit or 5, 10)
        )

    def get_unresolved_priorities(farm_id: str) -> list:
        return fcs.get_unresolved_priorities(db, org_id, farm_id)

    def get_morning_evening_comparison(farm_id: str, house_id: str) -> dict:
        latest = fcs.get_latest_flock_check(db, org_id, farm_id, house_id)
        if not latest:
            return {"available": False}
        comparison = latest.get("morning_comparison")
        if comparison is None:
            recent = fcs.get_flock_history(db, org_id, farm_id, house_id, limit=20)
            farm = fcs.get_farm(db, org_id, farm_id)
            comparison = comparison_service.build_morning_evening_comparison(
                recent, latest, farm_timezone=(farm or {}).get("timezone")
            )
        return {"available": comparison is not None, **(comparison or {})}

    def search_poultry_knowledge(
        query: str, category: str | None = None, production_type: str | None = None, top_k: int | None = None
    ) -> list:
        return knowledge_service.search_poultry_knowledge(
            db, query, category=category, production_type=production_type, top_k=min(top_k or 5, 8)
        )

    def create_agent_recommendation(
        farm_id: str,
        house_id: str | None,
        title: str,
        summary: str,
        priority: str,
        recommended_actions: list[str] | None = None,
        rec_type: str = "monitor",
    ) -> dict:
        """SAFE WRITE: creates a record for human review. Never resolves an
        alert, never assigns anyone, never notifies anyone - it only makes a
        recommendation visible in the app."""
        now = datetime.now(timezone.utc).isoformat()
        doc = {
            "farm_id": farm_id,
            "house_id": house_id,
            "type": rec_type,
            "priority": priority,
            "title": title,
            "summary": summary,
            "recommended_actions": recommended_actions or [],
            "status": "open",
            "created_at": now,
            "acknowledged_at": None,
            "completed_at": None,
        }
        doc_ref = agent_recommendations_ref(db, org_id).document()
        doc_ref.set(doc)
        return {"id": doc_ref.id, **doc}

    specs: list[Tool] = [
        Tool("get_farm_status", "Overall farm status: houses, house comparison, active alerts, missing Morning Checks today.",
             {"type": "object", "properties": {"farm_id": {"type": "string"}}, "required": ["farm_id"]}, READ, get_farm_status),
        Tool("get_house_status", "Full current status of one house: flock, latest check, today's morning/evening checks, alerts, recent inspections, trend insights.",
             _house_history_params(), READ, get_house_status),
        Tool("get_current_flock", "The active (or most recent) flock placed in a house.",
             _house_history_params(), READ, get_current_flock),
        Tool("get_latest_flock_check", "The single most recent Flock Check recorded for a house.",
             _house_history_params(), READ, get_latest_flock_check),
        Tool("get_morning_check", "Today's Morning Check for a house, if one was recorded.",
             _house_history_params(), READ, get_morning_check),
        Tool("get_evening_check", "Today's Evening Check for a house, if one was recorded.",
             _house_history_params(), READ, get_evening_check),
        Tool("get_morning_evening_comparison", "Structured diff between today's Morning Check and the house's latest check (mortality/feed/water/activity/risk change).",
             _house_history_params(), READ, get_morning_evening_comparison),
        Tool("get_flock_history", "Recent Flock Checks for a house, newest first, with all recorded fields.",
             _house_history_params(), READ, get_flock_history),
        Tool("get_risk_history", "Recent risk score/status per check for a house.",
             _house_history_params(), READ, get_risk_history),
        Tool("get_mortality_history", "Recent mortality counts per check for a house.",
             _house_history_params(), READ, get_mortality_history),
        Tool("get_feed_history", "Recent feed_kg per check for a house.",
             _house_history_params(), READ, get_feed_history),
        Tool("get_water_history", "Recent water level/liters per check for a house.",
             _house_history_params(), READ, get_water_history),
        Tool("get_active_alerts", "Currently open (non-resolved) alerts, optionally filtered to a farm and/or house.",
             {"type": "object", "properties": {"farm_id": {"type": "string"}, "house_id": {"type": "string"}}}, READ, get_active_alerts),
        Tool("get_recent_inspections", "Recent inspection records for a house (finding category, findings, action taken).",
             _house_history_params(), READ, get_recent_inspections),
        Tool("get_house_comparison", "Latest risk score per house in a farm, worst-first - the same data the AI Radar shows.",
             {"type": "object", "properties": {"farm_id": {"type": "string"}}, "required": ["farm_id"]}, READ, get_house_comparison),
        Tool("get_trend_insights", "Deterministic pattern detection for a house (e.g. feed declining 3 checks running) - never guess whether a trend exists, this tool already decided.",
             _house_history_params(), READ, get_trend_insights),
        Tool("get_previous_similar_inspections", "Past inspections on this house, optionally filtered to a finding_category, for historical context.",
             _house_history_params({"finding_category": {"type": "string"}}), READ, get_previous_similar_inspections),
        Tool("get_unresolved_priorities", "Houses in this farm with an open alert that has no completed inspection yet.",
             {"type": "object", "properties": {"farm_id": {"type": "string"}}, "required": ["farm_id"]}, READ, get_unresolved_priorities),
        Tool(
            "search_poultry_knowledge",
            "Searches the APPROVED poultry-management reference knowledge base (not farm data) for general guidance. "
            "Only call this when farm data alone doesn't answer the question - e.g. 'what should I check when water use drops'. "
            "Never use it to fill in a missing farm measurement.",
            {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "category": {"type": "string"},
                    "production_type": {"type": "string"},
                    "top_k": {"type": "integer"},
                },
                "required": ["query"],
            },
            READ,
            search_poultry_knowledge,
        ),
        Tool(
            "create_agent_recommendation",
            "Creates a recommendation record for a farmer to review (SAFE WRITE - never resolves an alert or notifies anyone). "
            "Use only when the investigation concludes something worth the farmer's attention.",
            {
                "type": "object",
                "properties": {
                    "farm_id": {"type": "string"},
                    "house_id": {"type": "string"},
                    "title": {"type": "string"},
                    "summary": {"type": "string"},
                    "priority": {"type": "string", "enum": ["low", "medium", "high", "urgent"]},
                    "recommended_actions": {"type": "array", "items": {"type": "string"}},
                    "rec_type": {"type": "string", "enum": ["inspection", "monitor", "follow_up", "summary"]},
                },
                "required": ["farm_id", "title", "summary", "priority"],
            },
            SAFE_WRITE,
            create_agent_recommendation,
        ),
    ]
    return {tool.name: tool for tool in specs}


def tool_schemas(registry: dict[str, Tool]) -> list[dict]:
    return [tool.to_openai_schema() for tool in registry.values()]
