"""Frontend-facing surface for the FlockGuard Agent's output: recommendations
from event-triggered investigations, and the underlying run audit log.

The agent itself is never called directly from these routes - it only ever
runs via app/agent/event_handlers.py (background, on a Flock Check
submission) or app/api/routes/ask.py (a farmer's question). This file is
purely read + human-review-state-change on what the agent already produced.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from google.cloud.firestore import Client, Query

from app.core.firestore import get_firestore_client
from app.core.permissions import get_current_membership
from app.core.refs import agent_recommendations_ref, agent_runs_ref

router = APIRouter(prefix="/agent", tags=["agent"])


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.get("/recommendations")
def list_recommendations(
    farm_id: str | None = None,
    house_id: str | None = None,
    status: str | None = None,
    membership: dict = Depends(get_current_membership),
    db: Client = Depends(get_firestore_client),
):
    docs = agent_recommendations_ref(db, membership["org_id"]).order_by(
        "created_at", direction=Query.DESCENDING
    ).stream()
    results = [{"id": d.id, **d.to_dict()} for d in docs]
    if farm_id:
        results = [r for r in results if r.get("farm_id") == farm_id]
    if house_id:
        results = [r for r in results if r.get("house_id") == house_id]
    if status:
        results = [r for r in results if r.get("status") == status]
    return results


def _update_recommendation_status(
    db: Client, org_id: str, recommendation_id: str, *, status: str, timestamp_field: str
) -> dict:
    doc_ref = agent_recommendations_ref(db, org_id).document(recommendation_id)
    if not doc_ref.get().exists:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    updates = {"status": status, timestamp_field: _now_iso()}
    doc_ref.update(updates)
    return {"id": recommendation_id, **updates}


@router.post("/recommendations/{recommendation_id}/acknowledge")
def acknowledge_recommendation(
    recommendation_id: str,
    membership: dict = Depends(get_current_membership),
    db: Client = Depends(get_firestore_client),
):
    return _update_recommendation_status(
        db, membership["org_id"], recommendation_id, status="acknowledged", timestamp_field="acknowledged_at"
    )


@router.post("/recommendations/{recommendation_id}/complete")
def complete_recommendation(
    recommendation_id: str,
    membership: dict = Depends(get_current_membership),
    db: Client = Depends(get_firestore_client),
):
    return _update_recommendation_status(
        db, membership["org_id"], recommendation_id, status="completed", timestamp_field="completed_at"
    )


@router.post("/recommendations/{recommendation_id}/dismiss")
def dismiss_recommendation(
    recommendation_id: str,
    membership: dict = Depends(get_current_membership),
    db: Client = Depends(get_firestore_client),
):
    return _update_recommendation_status(
        db, membership["org_id"], recommendation_id, status="dismissed", timestamp_field="completed_at"
    )


@router.get("/runs")
def list_agent_runs(
    farm_id: str | None = None,
    house_id: str | None = None,
    limit: int = 20,
    membership: dict = Depends(get_current_membership),
    db: Client = Depends(get_firestore_client),
):
    """Audit log for debugging, pilot evaluation, and AI cost analysis -
    never includes raw model chain-of-thought (see AgentState.to_run_document)."""
    docs = agent_runs_ref(db, membership["org_id"]).order_by("created_at", direction=Query.DESCENDING).stream()
    results = [{"id": d.id, **d.to_dict()} for d in docs]
    if farm_id:
        results = [r for r in results if r.get("farm_id") == farm_id]
    if house_id:
        results = [r for r in results if r.get("house_id") == house_id]
    return results[: min(limit, 100)]
