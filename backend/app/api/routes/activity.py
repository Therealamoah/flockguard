"""Heartbeat from the farm app - see app/services/activity_service.py for
how this becomes "online now", DAU/WAU/MAU and dormant users in the admin
console. Any signed-in user may call it; it only ever writes their own row."""

from fastapi import APIRouter, Depends
from google.cloud.firestore import Client

from app.core.firebase import get_current_user
from app.core.firestore import get_firestore_client
from app.models.schemas import HeartbeatRequest
from app.services import activity_service

router = APIRouter(prefix="/activity", tags=["activity"])


@router.post("/heartbeat", status_code=204)
def heartbeat(
    payload: HeartbeatRequest,
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_firestore_client),
):
    activity_service.record_heartbeat(db, user, path=payload.path)
