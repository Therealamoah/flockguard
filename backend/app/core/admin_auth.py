"""Platform-admin (FlockGuard operator) access - a level ABOVE every
organization, completely separate from the OWNER/MANAGER/WORKER roles in
app/core/roles.py, which only ever apply inside one org.

Granted by a Firebase custom claim, `platform_admin: true`, set only by
backend/scripts/grant_platform_admin.py (Admin SDK, run by a human with
the service account) - no API route can grant or revoke it, so a
compromised admin session can't mint more admins.
"""

from fastapi import Depends, HTTPException

from app.core.firebase import get_current_user


def is_platform_admin(user: dict) -> bool:
    return user.get("platform_admin") is True


async def require_platform_admin(user: dict = Depends(get_current_user)) -> dict:
    if not is_platform_admin(user):
        raise HTTPException(status_code=403, detail="Platform admin access required")
    return user
