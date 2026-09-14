"""Backend-enforced role checks for the Team/Settings/Billing surface.

Every existing route (farms, houses, flocks, flock_checks, alerts, ask,
analytics, inspections, media) keeps using `get_current_org_id` exactly as
before - OWNER, MANAGER and WORKER are all allowed to do all of that today
(submit checks, run inspections, use Ask FlockGuard, view Radar/analytics),
matching the permission matrix's MANAGER/WORKER lists. Only the new
management surface (team, settings, billing, danger zone) needs a role
check, which is what lives here.

Hiding a frontend button is never sufficient - every one of these
dependencies runs server-side and 403s before any handler code executes.
"""

from fastapi import Depends, HTTPException

from app.core.firebase import get_current_user
from app.core.firestore import get_firestore_client
from app.core.roles import Role
from app.services.membership_service import get_or_create_membership
from google.cloud.firestore import Client


async def get_current_membership(
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_firestore_client),
) -> dict:
    org_id = user.get("org_id", user["uid"])
    membership = get_or_create_membership(db, user, org_id)
    if membership is None or membership.get("status") != "active":
        raise HTTPException(status_code=403, detail="No active membership in this organization")
    return {**membership, "org_id": org_id}


def require_role(*allowed_roles: Role):
    """Dependency factory: `Depends(require_role(Role.OWNER))`, etc."""
    allowed = {r.value for r in allowed_roles}

    async def _dependency(membership: dict = Depends(get_current_membership)) -> dict:
        if membership["role"] not in allowed:
            raise HTTPException(status_code=403, detail="You don't have permission to do this")
        return membership

    return _dependency


require_owner = require_role(Role.OWNER)
require_manager_or_owner = require_role(Role.OWNER, Role.MANAGER)
