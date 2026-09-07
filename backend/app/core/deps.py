from fastapi import Depends

from app.core.firebase import get_current_user


async def get_current_org_id(user: dict = Depends(get_current_user)) -> str:
    """Resolves the caller's organization from Firebase custom claims.

    Falls back to the user's own uid so a solo farmer without an
    organization membership still gets an isolated data scope.
    """
    return user.get("org_id", user["uid"])
