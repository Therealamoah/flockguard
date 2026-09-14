import logging
from email.message import EmailMessage

import aiosmtplib

from app.core.config import settings

_logger = logging.getLogger(__name__)


async def send_invite_email(*, to_email: str, farm_name: str, role: str, invited_by_email: str | None) -> bool:
    """Emails a team invite via SMTP (e.g. Gmail + an App Password).

    Best-effort: a failed or unconfigured send must never block creating the
    invitation itself - the invite still works if the person just signs in
    directly with the invited email (see team.py::my_invitations), this is
    only a courtesy notification. Returns whether the email actually went
    out, so the caller can tell the frontend whether to fall back to
    "share this invite directly".
    """
    if not settings.smtp_username or not settings.smtp_password:
        _logger.info("SMTP not configured - skipping invite email to %s", to_email)
        return False

    from_email = settings.smtp_from_email or settings.smtp_username
    inviter_line = f" by {invited_by_email}" if invited_by_email else ""

    message = EmailMessage()
    message["From"] = f"{settings.smtp_from_name} <{from_email}>"
    message["To"] = to_email
    message["Subject"] = f"You've been invited to join {farm_name} on FlockGuard"

    message.set_content(
        f"You've been invited{inviter_line} to join {farm_name} on FlockGuard as a {role}.\n\n"
        f"Sign in or create an account at {settings.app_public_url} using this email address "
        f"({to_email}) and the invitation will be waiting for you to accept.\n\n"
        "- FlockGuard"
    )
    message.add_alternative(
        f"""\
<div style="font-family: -apple-system, sans-serif; max-width: 480px; margin: 0 auto; color: #16222B;">
  <h2 style="color: #1B4332; margin-bottom: 4px;">You've been invited to FlockGuard</h2>
  <p>You've been invited{inviter_line} to join <strong>{farm_name}</strong> as a <strong>{role}</strong>.</p>
  <p>
    <a href="{settings.app_public_url}/register"
       style="display:inline-block;background:#1B4332;color:#fff;padding:10px 22px;
              border-radius:9999px;text-decoration:none;font-weight:600;">
      Accept invitation
    </a>
  </p>
  <p style="font-size:13px;color:#64748b;">
    Sign in or create an account using <strong>{to_email}</strong> to see and accept it.
  </p>
</div>
""",
        subtype="html",
    )

    try:
        await aiosmtplib.send(
            message,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            start_tls=True,
            username=settings.smtp_username,
            password=settings.smtp_password,
        )
        return True
    except Exception:
        _logger.exception("Failed to send invite email to %s", to_email)
        return False
