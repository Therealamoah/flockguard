import json

import firebase_admin
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from firebase_admin import auth as firebase_auth, credentials

from app.core.config import settings

_bearer_scheme = HTTPBearer(auto_error=False)


def _init_firebase_app() -> firebase_admin.App | None:
    if firebase_admin._apps:
        return firebase_admin.get_app()

    try:
        if settings.firebase_service_account_json:
            cred = credentials.Certificate(json.loads(settings.firebase_service_account_json))
            return firebase_admin.initialize_app(cred)

        # Falls back to Application Default Credentials (e.g. on Render/GCP
        # with GOOGLE_APPLICATION_CREDENTIALS set), or emulator use locally.
        return firebase_admin.initialize_app()
    except Exception:  # noqa: BLE001 - no credentials configured yet in this env
        return None


_init_firebase_app()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> dict:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
        )

    try:
        return firebase_auth.verify_id_token(credentials.credentials)
    except Exception as exc:  # noqa: BLE001 - surfaced as a generic auth failure
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token",
        ) from exc
