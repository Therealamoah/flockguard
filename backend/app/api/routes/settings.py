"""Farm settings: profile (incl. timezone), check schedule, notification
preferences, AI preferences, danger zone, and self-service account updates.

Storage decision: settings live as new, additive fields directly on the
existing `organizations/{org}/farms/{farm}` document - no new collection,
no migration. A farm document created before this feature existed simply
lacks these fields; every reader here merges in `DEFAULT_SETTINGS` rather
than requiring them to be present, so old farms keep working unmodified
and never need backfilling just to be readable.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from firebase_admin import auth as firebase_auth
from google.cloud.firestore import Client

from app.core.firebase import get_current_user
from app.core.firestore import get_firestore_client
from app.core.permissions import get_current_membership, require_manager_or_owner, require_owner
from app.core.refs import farms_ref
from app.models.schemas import AccountUpdate, DeleteFarmRequest, FarmSettingsUpdate

router = APIRouter(tags=["settings"])

DEFAULT_SETTINGS = {
    "country": None,
    # None means "not set yet" - comparison_service/farm_context_service
    # both treat that as UTC, matching this app's behavior before farm
    # timezones existed.
    "timezone": None,
    "temperature_unit": "celsius",
    "weight_unit": "kg",
    "contact_number": None,
    "morning_check_enabled": True,
    "morning_check_start": "06:00",
    "morning_check_end": "10:00",
    "evening_check_enabled": True,
    "evening_check_start": "16:00",
    "evening_check_end": "20:00",
    "notification_preferences": {
        "critical_alerts": True,
        "warning_alerts": True,
        "watch_alerts": False,
        "morning_check_reminder": True,
        "evening_check_reminder": True,
        "daily_farm_brief": True,
        # Only in_app is real. push/email default False (not built yet);
        # whatsapp/sms are permanently "coming_soon" - never advertise a
        # channel as working before a provider is actually wired up.
        "channels": {"in_app": True, "push": False, "email": False, "whatsapp": "coming_soon", "sms": "coming_soon"},
    },
    "ai_preferences": {
        "ai_explanations_enabled": True,
        "daily_ai_brief_enabled": True,
        "proactive_insights_enabled": True,
    },
    "archived": False,
}

RISK_METHOD_INFO = {
    "name": "FlockGuard Standard",
    "description": "Risk scores are generated from your flock records and recent historical patterns.",
    "disclaimer": "FlockGuard provides early-warning decision support and does not provide veterinary diagnosis.",
    # Deliberately not user-configurable - Normal/Watch/Warning/Critical
    # thresholds and factor weights (app/risk_engine/) stay FlockGuard-controlled.
    "configurable": False,
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _farm_or_404(db: Client, org_id: str, farm_id: str):
    doc_ref = farms_ref(db, org_id).document(farm_id)
    snap = doc_ref.get()
    if not snap.exists:
        raise HTTPException(status_code=404, detail="Farm not found")
    return doc_ref, snap.to_dict()


@router.get("/settings")
def get_settings(
    farm_id: str,
    membership: dict = Depends(get_current_membership),
    db: Client = Depends(get_firestore_client),
):
    _, data = _farm_or_404(db, membership["org_id"], farm_id)
    merged = {**DEFAULT_SETTINGS, **data, "id": farm_id}
    merged["risk_method"] = RISK_METHOD_INFO
    return merged


@router.patch("/settings")
def update_settings(
    farm_id: str,
    payload: FarmSettingsUpdate,
    membership: dict = Depends(require_manager_or_owner),
    db: Client = Depends(get_firestore_client),
):
    doc_ref, _ = _farm_or_404(db, membership["org_id"], farm_id)
    updates = payload.model_dump(exclude_unset=True, mode="json")
    if not updates:
        raise HTTPException(status_code=422, detail="No settings provided")
    updates["updated_at"] = _now_iso()
    doc_ref.update(updates)
    return {"id": farm_id, **updates}


@router.patch("/settings/account")
def update_account(
    payload: AccountUpdate,
    user: dict = Depends(get_current_user),
):
    """Self-service only - updates the caller's own Firebase Auth profile.
    No org role required; nothing here touches organization data."""
    firebase_auth.update_user(user["uid"], display_name=payload.display_name)
    return {"display_name": payload.display_name}


@router.post("/settings/farms/{farm_id}/archive")
def archive_farm(
    farm_id: str,
    membership: dict = Depends(require_owner),
    db: Client = Depends(get_firestore_client),
):
    doc_ref, _ = _farm_or_404(db, membership["org_id"], farm_id)
    doc_ref.update({"archived": True, "archived_at": _now_iso()})
    return {"id": farm_id, "archived": True}


@router.post("/settings/farms/{farm_id}/unarchive")
def unarchive_farm(
    farm_id: str,
    membership: dict = Depends(require_owner),
    db: Client = Depends(get_firestore_client),
):
    doc_ref, _ = _farm_or_404(db, membership["org_id"], farm_id)
    doc_ref.update({"archived": False, "archived_at": None})
    return {"id": farm_id, "archived": False}


@router.post("/settings/farms/{farm_id}/delete")
def delete_farm(
    farm_id: str,
    payload: DeleteFarmRequest,
    membership: dict = Depends(require_owner),
    db: Client = Depends(get_firestore_client),
):
    """Guarded and intentionally disabled. Permanent deletion needs a safe
    cascade across houses/flocks/flock_checks/alerts/inspections/media
    (Cloudinary assets included), which this pilot doesn't implement yet -
    shipping a partial delete would leave orphaned data, which is worse
    than not offering delete at all. Archive is the real, working,
    reversible alternative. The confirmation contract below (owner role +
    typed confirmation) is enforced now so the UI/API shape doesn't need
    to change again once real cascade delete is built.
    """
    doc_ref, data = _farm_or_404(db, membership["org_id"], farm_id)
    farm_name = data.get("name", "")
    if payload.confirmation not in (farm_name, "DELETE"):
        raise HTTPException(status_code=400, detail="Confirmation text does not match the farm name or 'DELETE'")

    raise HTTPException(
        status_code=501,
        detail=(
            "Permanent farm deletion isn't available yet in this pilot "
            "(no safe cascade-delete across houses/flocks/checks/alerts/inspections/media). "
            "Use Archive instead - it's reversible and fully supported."
        ),
    )
