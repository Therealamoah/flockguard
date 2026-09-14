"""Real, live usage against an org's plan limits (see PILOT_LIMITS in
app/api/routes/billing.py).

Houses/birds/team seats are counted straight from Firestore on every call -
there's no separate counter for them to drift out of sync with reality.
AI requests and storage ARE separate counters (a month's request count and a
lifetime storage total aren't something you can re-derive by re-scanning
Firestore), incremented at the point of use: app/agent/flockguard_agent.py
and app/api/routes/ask.py for AI requests, app/api/routes/media.py for
storage.

`enforce_limit` is called before the action that would create the resource
(not after), so a plan's cap actually blocks the (N+1)th house/bird/team
seat/AI request rather than just describing usage after the fact.
"""

from datetime import datetime, timezone

from fastapi import HTTPException
from google.cloud.firestore import Client, Increment

from app.core.refs import (
    farms_ref,
    flocks_ref,
    houses_ref,
    invitations_ref,
    members_ref,
    organization_ref,
    subscription_ref,
)
from app.services.farm_context_service import get_latest_flock_check


def current_period_key() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def usage_periods_ref(db: Client, org_id: str):
    return organization_ref(db, org_id).collection("usage_periods")


def count_houses(db: Client, org_id: str) -> int:
    return sum(1 for farm_doc in farms_ref(db, org_id).stream() for _ in houses_ref(db, org_id, farm_doc.id).stream())


def count_birds(db: Client, org_id: str) -> int:
    """Mirrors OverviewPage.jsx's own bird-count logic: latest check's
    bird_count first, active flock's initial_bird_count as fallback - kept
    consistent so this number never disagrees with what the farmer sees."""
    total = 0
    for farm_doc in farms_ref(db, org_id).stream():
        for house_doc in houses_ref(db, org_id, farm_doc.id).stream():
            latest = get_latest_flock_check(db, org_id, farm_doc.id, house_doc.id)
            if latest and latest.get("bird_count") is not None:
                total += latest["bird_count"]
            else:
                active_flocks = flocks_ref(db, org_id, farm_doc.id, house_doc.id).where(
                    "status", "==", "active"
                ).stream()
                total += sum(f.to_dict().get("initial_bird_count", 0) for f in active_flocks)
    return total


def count_team_seats(db: Client, org_id: str) -> int:
    """Active members + still-pending invitations - a plan's seat cap
    should block a 6th invite even before the prior ones are accepted, not
    only once they are."""
    active = sum(1 for d in members_ref(db, org_id).stream() if d.to_dict().get("status") == "active")
    pending = sum(1 for d in invitations_ref(db, org_id).stream() if d.to_dict().get("status") == "pending")
    return active + pending


def enforce_limit(current: int, limit: int | None, *, resource: str, plan: str) -> None:
    """Raises 402 Payment Required once `current` has reached `limit`.
    A None limit means unlimited (a future paid plan may leave some metric
    uncapped) - never treated as "0 allowed"."""
    if limit is not None and current >= limit:
        raise HTTPException(
            status_code=402,
            detail=(
                f"Your {plan.upper()} plan's {resource} limit ({limit}) has been reached. "
                "Contact support to discuss upgrading."
            ),
        )


def increment_ai_requests(db: Client, org_id: str, count: int = 1) -> None:
    usage_periods_ref(db, org_id).document(current_period_key()).set({"ai_requests": Increment(count)}, merge=True)


def get_ai_requests_this_month(db: Client, org_id: str) -> int:
    doc = usage_periods_ref(db, org_id).document(current_period_key()).get()
    return (doc.to_dict() or {}).get("ai_requests", 0) if doc.exists else 0


def increment_storage_bytes(db: Client, org_id: str, size_bytes: int) -> None:
    subscription_ref(db, org_id).set({"storage_bytes": Increment(size_bytes)}, merge=True)


def get_storage_bytes(db: Client, org_id: str) -> int:
    doc = subscription_ref(db, org_id).get()
    return (doc.to_dict() or {}).get("storage_bytes", 0) if doc.exists else 0
