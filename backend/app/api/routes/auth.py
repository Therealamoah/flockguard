"""Unauthenticated auth-adjacent endpoints - nothing here sits behind
get_current_user, by definition (you don't have a session yet when you've
forgotten your password).

Password reset is backend-mediated specifically so the email itself can be
FlockGuard's own branded template (see app/services/email_service.py)
instead of Firebase Auth's default, unbranded, copy-paste-only email. The
underlying reset link is still a real Firebase Auth action link generated
via the Admin SDK - only which email carries it, and how it looks, changes.
"""

import logging

from fastapi import APIRouter, Request
from firebase_admin import auth as firebase_auth

from app.core.config import settings
from app.core.limiter import limiter
from app.models.schemas import ForgotPasswordRequest
from app.services.email_service import send_password_reset_email

_logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

GENERIC_RESPONSE = {"message": "If an account exists for this email, a password reset link has been sent."}


@router.post("/forgot-password")
@limiter.limit(settings.rate_limit_password_reset)
async def forgot_password(request: Request, payload: ForgotPasswordRequest):
    """Always returns the same generic response regardless of whether the
    email actually has an account - confirming/denying that would let
    anyone enumerate registered users one guess at a time."""
    try:
        reset_link = firebase_auth.generate_password_reset_link(payload.email)
    except firebase_auth.UserNotFoundError:
        return GENERIC_RESPONSE
    except Exception:  # noqa: BLE001 - Firebase Admin down/misconfigured must not break this response
        _logger.exception("Failed to generate password reset link for %s", payload.email)
        return GENERIC_RESPONSE

    await send_password_reset_email(to_email=payload.email, reset_link=reset_link)
    return GENERIC_RESPONSE
