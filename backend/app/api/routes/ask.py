from fastapi import APIRouter, Depends
from google.cloud.firestore import Client, Query

from app.core.deps import get_current_org_id
from app.core.firestore import get_firestore_client
from app.core.refs import houses_ref
from app.models.schemas import AskRequest
from app.services.grok_service import grok_service

router = APIRouter(prefix="/ask", tags=["ask-flockguard"])

SYSTEM_PROMPT = (
    "You are Ask FlockGuard, the AI assistant inside the FlockGuard poultry "
    "monitoring platform. You explain risk scores, alerts, and trends that "
    "FlockGuard's Risk Engine has already calculated. You are NOT a disease "
    "diagnosis tool - never diagnose illnesses. Speak plainly to a poultry "
    "farmer, reference the house/risk data given to you, and suggest what to "
    "inspect next rather than what disease it might be."
)


def _house_name(db: Client, org_id: str, farm_id: str, house_id: str, cache: dict) -> str:
    key = (farm_id, house_id)
    if key not in cache:
        doc = houses_ref(db, org_id, farm_id).document(house_id).get()
        cache[key] = doc.to_dict().get("name", house_id) if doc.exists else house_id
    return cache[key]


def _recent_alerts_summary(db: Client, org_id: str) -> str:
    # Filtered in Python rather than with a Firestore `.where(...)` alongside
    # `.order_by("created_at")` on a different field - that combination needs
    # a composite index that doesn't exist in this project and would 500.
    alerts = (
        db.collection("organizations")
        .document(org_id)
        .collection("alerts")
        .order_by("created_at", direction=Query.DESCENDING)
        .stream()
    )
    open_alerts = [a for a in (doc.to_dict() for doc in alerts) if not a.get("acknowledged")][:10]
    house_name_cache: dict = {}
    lines = [
        f"- {_house_name(db, org_id, a.get('farm_id'), a.get('house_id'), house_name_cache)}: "
        f"risk {a.get('score')} ({a.get('status')})"
        for a in open_alerts
    ]
    return "\n".join(lines) if lines else "No open alerts."


@router.post("")
async def ask_flockguard(
    payload: AskRequest,
    org_id: str = Depends(get_current_org_id),
    db: Client = Depends(get_firestore_client),
):
    context = _recent_alerts_summary(db, org_id)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": f"Current open alerts:\n{context}"},
        {"role": "user", "content": payload.question},
    ]
    answer = await grok_service.chat(messages)
    return {"answer": answer}
