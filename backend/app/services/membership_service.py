"""Organization membership: backfill, lookup, and Firebase custom-claim
management for multi-user access.

How a second person ends up in the same org as the owner, without any
change to the dozens of existing routes that already scope everything by
`get_current_org_id` (backend/app/core/deps.py):

1. Every org today is a solo owner whose `org_id` equals their own `uid`
   (no code has ever set the `org_id` custom claim - confirmed by grep).
2. When an invitation is accepted (see app/api/routes/team.py), we create
   a membership doc AND set the invited user's Firebase `org_id` custom
   claim to the inviting owner's uid.
3. On their next ID token (forced refresh after accept, or natural
   refresh), `get_current_org_id` resolves them into the SAME org as
   everyone else automatically - every existing farm/house/check/alert
   route keeps working unmodified for every role.

Role/permission checks for the *new* team/settings/billing surface live in
app/core/permissions.py, which builds on `get_current_membership` below.
"""

from datetime import datetime, timezone

from firebase_admin import auth as firebase_auth
from google.cloud.firestore import Client

from app.core.refs import members_ref
from app.core.roles import Role


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_or_create_membership(db: Client, user: dict, org_id: str) -> dict | None:
    """Returns the caller's membership doc, self-healing the owner case.

    For every organization created before this feature existed, no
    `members` collection exists yet - rather than requiring a migration
    script or wiping Firestore, the very first authenticated request from
    that org's owner (org_id == their own uid) silently backfills their
    OWNER membership document. Returns None only for the genuinely invalid
    state of a non-owner org_id with no membership record (shouldn't
    happen via the app's own flows, but must never be treated as owner).
    """
    uid = user["uid"]
    doc_ref = members_ref(db, org_id).document(uid)
    snap = doc_ref.get()
    if snap.exists:
        return {"id": snap.id, **snap.to_dict()}

    if org_id != uid:
        return None

    membership = {
        "user_id": uid,
        "email": user.get("email"),
        "display_name": user.get("name") or user.get("email"),
        "role": Role.OWNER.value,
        "status": "active",
        "joined_at": _now(),
        "invited_by": None,
        "updated_at": _now(),
    }
    doc_ref.set(membership)
    return {"id": uid, **membership}


def count_active_owners(db: Client, org_id: str) -> int:
    docs = members_ref(db, org_id).where("role", "==", Role.OWNER.value).where("status", "==", "active").stream()
    return sum(1 for _ in docs)


def get_notification_emails(db: Client, org_id: str) -> list[str]:
    """Emails for the people who should hear about something needing
    attention (e.g. a new alert) - active owners and managers, not workers
    or anyone who's left/been removed."""
    emails = []
    for doc in members_ref(db, org_id).where("status", "==", "active").stream():
        data = doc.to_dict()
        if data.get("role") in (Role.OWNER.value, Role.MANAGER.value) and data.get("email"):
            emails.append(data["email"])
    return emails


def get_notification_uids(db: Client, org_id: str) -> list[str]:
    """Same audience as get_notification_emails (active owners/managers) but
    as member uids - used by app/services/push_service.py to look up each
    person's registered push tokens, which are stored per-uid, not
    per-email."""
    uids = []
    for doc in members_ref(db, org_id).where("status", "==", "active").stream():
        data = doc.to_dict()
        if data.get("role") in (Role.OWNER.value, Role.MANAGER.value):
            uids.append(doc.id)
    return uids


def set_org_claim(uid: str, org_id: str) -> None:
    """Grants org access on the invited user's Firebase Auth token.

    Preserves any other custom claims already on the account rather than
    clobbering them.
    """
    try:
        existing = firebase_auth.get_user(uid).custom_claims or {}
    except Exception:  # noqa: BLE001 - best-effort read, still safe to overwrite below
        existing = {}
    firebase_auth.set_custom_user_claims(uid, {**existing, "org_id": org_id})


def clear_org_claim(uid: str) -> None:
    """Revokes org access - used when removing a member. Also revokes their
    refresh tokens so access is cut immediately rather than waiting for
    their current token to expire naturally (up to ~1 hour)."""
    try:
        existing = firebase_auth.get_user(uid).custom_claims or {}
    except Exception:  # noqa: BLE001
        existing = {}
    existing.pop("org_id", None)
    firebase_auth.set_custom_user_claims(uid, existing)
    try:
        firebase_auth.revoke_refresh_tokens(uid)
    except Exception:  # noqa: BLE001 - best-effort; claim removal above is the primary control
        pass
