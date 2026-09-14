"""Event-driven agent triggering - invoked from route handlers via FastAPI
BackgroundTasks, so a Flock Check submission's HTTP response is never
delayed by, or fails because of, an AI investigation (see app/api/routes/
flock_checks.py). This is the "background execution" answer for section
60 of the architecture spec: FastAPI's own BackgroundTasks is sufficient
for this pilot's volume - no Celery/Redis/RabbitMQ/Kafka. A durable queue
would only become necessary once investigations need to survive a
process restart or run across multiple backend instances; document that
as the trigger for revisiting this, not "agentic sounds fancy."
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from google.cloud.firestore import Client

from app.agent.agent_router import select_skill_for_trigger
from app.agent.agent_state import AgentAssessment
from app.agent.flockguard_agent import run_agent
from app.core.refs import agent_recommendations_ref, agent_runs_ref

_logger = logging.getLogger(__name__)

RECOMMENDATION_WORTHY_PRIORITIES = {"high", "urgent"}


def _already_investigated(db: Client, org_id: str, source_event_id: str) -> bool:
    """Idempotency: never run a second investigation for the same event
    (a retried request, a duplicate background-task schedule, etc.)."""
    existing = agent_runs_ref(db, org_id).where("source_event_id", "==", source_event_id).limit(1).stream()
    return next(existing, None) is not None


def _persist_recommendation(
    db: Client, org_id: str, farm_id: str, run_id: str, assessment: AgentAssessment
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    first_sentence = assessment.summary.split(".")[0].strip() or assessment.summary
    doc = {
        "farm_id": farm_id,
        "house_id": assessment.house_id,
        "agent_run_id": run_id,
        "source_event_id": None,
        "type": "inspection" if assessment.requires_inspection else "monitor",
        "priority": assessment.priority.value,
        "title": first_sentence[:120],
        "summary": assessment.summary,
        "observed_data": assessment.observed_data,
        "calculated_signals": assessment.calculated_signals,
        "historical_context": assessment.historical_context,
        "knowledge_sources": [s.model_dump() for s in assessment.knowledge_sources],
        "recommended_actions": assessment.recommended_actions,
        "confidence": assessment.confidence.value,
        "status": "open",
        "created_at": now,
        "acknowledged_at": None,
        "completed_at": None,
    }
    agent_recommendations_ref(db, org_id).document().set(doc)


async def investigate_flock_check(
    db: Client,
    *,
    org_id: str,
    farm_id: str,
    house_id: str,
    flock_id: str | None,
    check_id: str,
    trigger: str,
) -> None:
    """Runs after the Flock Check's HTTP response has already been sent.
    Any failure here is logged, never surfaced to the farmer as a broken
    check submission - the check itself already saved successfully before
    this was even scheduled.

    `db` is passed in by the caller (the same Firestore client the
    request itself resolved via `Depends(get_firestore_client)`) rather
    than fetched fresh here - this is a background task, not a route, so
    it has no dependency injection of its own, and fetching a client
    independently would silently bypass any client the caller (including
    tests, via dependency_overrides) was supposed to use.
    """
    try:
        if _already_investigated(db, org_id, check_id):
            return

        skill = select_skill_for_trigger(trigger)
        state = await run_agent(
            db,
            org_id=org_id,
            trigger=trigger,
            skill=skill,
            farm_id=farm_id,
            house_id=house_id,
            flock_id=flock_id,
            source_event_id=check_id,
        )
        agent_runs_ref(db, org_id).document(state.run_id).set(state.to_run_document())

        if state.assessment and state.assessment.priority.value in RECOMMENDATION_WORTHY_PRIORITIES:
            _persist_recommendation(db, org_id, farm_id, state.run_id, state.assessment)
    except Exception:  # noqa: BLE001 - a background investigation must never raise into the task runner
        _logger.exception("Background investigation failed for check %s", check_id)
