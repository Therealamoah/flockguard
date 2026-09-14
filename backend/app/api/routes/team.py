"""Team management: memberships, roles, invitations.

Every existing route (farms, houses, flock-checks, alerts, ask, analytics,
inspections, media) keeps using `get_current_org_id` completely unchanged -
once a member's `org_id` custom claim is set (see
app/services/membership_service.py), they automatically get the exact
same access every existing route already gives any authenticated caller
for their org. This file only adds the NEW surface: who's on the team,
inviting/removing/changing roles, and accepting an invitation.

Authorization is enforced here via app/core/permissions.py - never by the
frontend hiding a button.
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from google.cloud.firestore import Client

from app.core.firebase import get_current_user
from app.core.firestore import get_firestore_client
from app.core.permissions import get_current_membership, require_owner
from app.core.refs import farms_ref, invitations_ref, members_ref
from app.core.roles import Role
from app.models.schemas import AcceptInvitationRequest, InviteMemberRequest, UpdateMemberRoleRequest
from app.services.billing_service import get_subscription
from app.services.email_service import send_invite_email
from app.services.membership_service import clear_org_claim, count_active_owners, set_org_claim
from app.services.usage_service import count_team_seats, enforce_limit

router = APIRouter(prefix="/team", tags=["team"])

INVITATION_TTL_DAYS = 7


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.get("")
def list_team(
    membership: dict = Depends(get_current_membership),
    db: Client = Depends(get_firestore_client),
):
    """Visible to any active member (owner/manager/worker) - seeing who has
    access is not itself a sensitive management action; changing it is."""
    org_id = membership["org_id"]
    members = [{"id": d.id, **d.to_dict()} for d in members_ref(db, org_id).stream()]
    members.sort(key=lambda m: m.get("joined_at") or "")

    pending = [
        {"id": d.id, **d.to_dict()}
        for d in invitations_ref(db, org_id).stream()
        if d.to_dict().get("status") == "pending"
    ]
    pending.sort(key=lambda i: i.get("created_at") or "")

    return {"members": members, "pending_invitations": pending}


@router.post("/invitations", status_code=201)
async def create_invitation(
    payload: InviteMemberRequest,
    membership: dict = Depends(require_owner),
    db: Client = Depends(get_firestore_client),
):
    org_id = membership["org_id"]

    already_member = next(members_ref(db, org_id).where("email", "==", payload.email).limit(1).stream(), None)
    if already_member is not None:
        raise HTTPException(status_code=409, detail="This person is already on the team")

    same_email_invites = invitations_ref(db, org_id).where("email", "==", payload.email).stream()
    if any(d.to_dict().get("status") == "pending" for d in same_email_invites):
        raise HTTPException(status_code=409, detail="An invitation is already pending for this email")

    subscription = get_subscription(db, org_id)
    enforce_limit(
        count_team_seats(db, org_id),
        subscription.get("limits", {}).get("team_members"),
        resource="team seat",
        plan=subscription.get("plan", "pilot"),
    )

    now = datetime.now(timezone.utc)
    invitation = {
        "email": payload.email,
        "role": payload.role.value,
        "status": "pending",
        "invited_by": membership["user_id"],
        "invited_by_email": membership.get("email"),
        "created_at": now.isoformat(),
        "expires_at": (now + timedelta(days=INVITATION_TTL_DAYS)).isoformat(),
        "accepted_at": None,
    }
    doc_ref = invitations_ref(db, org_id).document()
    doc_ref.set(invitation)

    first_farm = next(farms_ref(db, org_id).limit(1).stream(), None)
    farm_name = (first_farm.to_dict().get("name") if first_farm else None) or "their farm"
    email_sent = await send_invite_email(
        to_email=payload.email,
        farm_name=farm_name,
        role=payload.role.value,
        invited_by_email=membership.get("email"),
    )

    return {"id": doc_ref.id, **invitation, "email_sent": email_sent}


@router.delete("/invitations/{invitation_id}")
def cancel_invitation(
    invitation_id: str,
    membership: dict = Depends(require_owner),
    db: Client = Depends(get_firestore_client),
):
    org_id = membership["org_id"]
    doc_ref = invitations_ref(db, org_id).document(invitation_id)
    if not doc_ref.get().exists:
        raise HTTPException(status_code=404, detail="Invitation not found")
    doc_ref.update({"status": "cancelled"})
    return {"id": invitation_id, "status": "cancelled"}


@router.patch("/members/{member_id}")
def update_member_role(
    member_id: str,
    payload: UpdateMemberRoleRequest,
    membership: dict = Depends(require_owner),
    db: Client = Depends(get_firestore_client),
):
    org_id = membership["org_id"]
    doc_ref = members_ref(db, org_id).document(member_id)
    snap = doc_ref.get()
    if not snap.exists:
        raise HTTPException(status_code=404, detail="Member not found")
    current = snap.to_dict()

    if (
        current.get("role") == Role.OWNER.value
        and payload.role != Role.OWNER
        and count_active_owners(db, org_id) <= 1
    ):
        raise HTTPException(status_code=400, detail="Cannot demote the organization's only owner")

    doc_ref.update({"role": payload.role.value, "updated_at": _now_iso()})
    return {"id": member_id, **current, "role": payload.role.value}


@router.delete("/members/{member_id}")
def remove_member(
    member_id: str,
    membership: dict = Depends(require_owner),
    db: Client = Depends(get_firestore_client),
):
    org_id = membership["org_id"]
    doc_ref = members_ref(db, org_id).document(member_id)
    snap = doc_ref.get()
    if not snap.exists:
        raise HTTPException(status_code=404, detail="Member not found")
    current = snap.to_dict()

    if current.get("role") == Role.OWNER.value and count_active_owners(db, org_id) <= 1:
        raise HTTPException(status_code=400, detail="Cannot remove the organization's only owner")

    doc_ref.delete()
    clear_org_claim(member_id)
    return {"id": member_id, "removed": True}


@router.get("/my-invitations")
def my_invitations(
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_firestore_client),
):
    """Collection-group query across every org's invitations - a brand-new
    user's own (solo) org has no invitations of its own, since invitations
    live under the INVITER's org. This is the only way for someone to
    discover "I've been invited" without already knowing which org to
    check, and it's still safe: it only ever matches the caller's own
    verified token email, never a client-supplied one.
    """
    email = (user.get("email") or "").lower()
    if not email:
        return []

    results = []
    docs = db.collection_group("invitations").where("email", "==", email).stream()
    for doc in docs:
        data = doc.to_dict()
        if data.get("status") != "pending":
            continue
        org_id = doc.reference.parent.parent.id
        results.append(
            {
                "id": doc.id,
                "org_id": org_id,
                "role": data.get("role"),
                "invited_by_email": data.get("invited_by_email"),
                "created_at": data.get("created_at"),
                "expires_at": data.get("expires_at"),
            }
        )
    return results


@router.post("/invitations/accept")
def accept_invitation(
    payload: AcceptInvitationRequest,
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_firestore_client),
):
    """Never lets someone join by supplying an arbitrary org_id: the
    invitation's stored email must match the CALLER'S OWN verified Firebase
    token email, not anything client-supplied."""
    doc_ref = invitations_ref(db, payload.org_id).document(payload.invitation_id)
    snap = doc_ref.get()
    if not snap.exists:
        raise HTTPException(status_code=404, detail="Invitation not found")
    invitation = snap.to_dict()

    if invitation.get("status") != "pending":
        raise HTTPException(status_code=400, detail="This invitation is no longer pending")

    caller_email = (user.get("email") or "").lower()
    if invitation.get("email") != caller_email:
        raise HTTPException(status_code=403, detail="This invitation was sent to a different email address")

    expires_at = invitation.get("expires_at")
    if expires_at and datetime.fromisoformat(expires_at) < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="This invitation has expired")

    now = _now_iso()
    member_doc = {
        "user_id": user["uid"],
        "email": user.get("email"),
        "display_name": user.get("name") or user.get("email"),
        "role": invitation["role"],
        "status": "active",
        "joined_at": now,
        "invited_by": invitation.get("invited_by"),
        "updated_at": now,
    }
    members_ref(db, payload.org_id).document(user["uid"]).set(member_doc)
    doc_ref.update({"status": "accepted", "accepted_at": now})
    set_org_claim(user["uid"], payload.org_id)

    return {
        "org_id": payload.org_id,
        "role": invitation["role"],
        "member": member_doc,
        "note": "Sign out and back in (or refresh your session) for the new access to take effect.",
    }
