"""Every outbound email FlockGuard sends - team invites, password resets,
and alert notifications - shares one branded HTML shell (_html_shell) so
they look and feel consistent, and one send helper (_send) so "best-effort,
SMTP-config-guarded, never raises" is enforced in exactly one place rather
than copy-pasted per email type.
"""

import logging
from email.message import EmailMessage

import aiosmtplib

from app.core.config import settings

_logger = logging.getLogger(__name__)

STATUS_COLORS = {"watch": "#B3811A", "warning": "#C05A1D", "critical": "#C8433A"}


def _html_shell(preheader: str, body_html: str) -> str:
    """The branded wrapper every email uses: a small preheader (the preview
    text some inboxes show next to the subject), a logo header, a white
    content card, and a footer - body_html is only ever the card's inner
    content, never anything layout-level, so every email stays visually
    consistent without repeating this markup.

    The logo is referenced by URL (app_public_url/logo-mark.png), not
    embedded - inline/base64 images are unreliable across email clients,
    and a real https URL is what actually renders once deployed (it won't
    load from a local dev server, which is expected and harmless).
    """
    return f"""\
<div style="display:none;max-height:0;overflow:hidden;opacity:0;">{preheader}</div>
<div style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:480px;margin:0 auto;background:#F6F5F1;padding:32px 16px;">
  <div style="text-align:center;margin-bottom:20px;">
    <img src="{settings.app_public_url}/logo-mark.png" alt="FlockGuard" width="40" height="40"
         style="display:inline-block;vertical-align:middle;border-radius:9px;" />
    <span style="display:inline-block;vertical-align:middle;margin-left:8px;font-weight:800;font-size:20px;color:#1B4332;">
      FlockGuard
    </span>
  </div>
  <div style="background:#ffffff;border-radius:16px;padding:28px 24px;color:#16222B;">
    {body_html}
  </div>
  <p style="text-align:center;font-size:11px;color:#94a3b8;margin-top:20px;">
    FlockGuard &middot; AI-native poultry early-warning platform
  </p>
</div>
"""


def _cta_button(text: str, url: str) -> str:
    """A real, generously-padded tap target (not just a text link) - the
    whole point is that a phone user can tap this cleanly instead of having
    to select and copy a raw URL."""
    return (
        f'<div style="text-align:center;margin:28px 0;">'
        f'<a href="{url}" style="display:inline-block;background:#1B4332;color:#ffffff;'
        f'padding:14px 32px;border-radius:9999px;text-decoration:none;font-weight:700;font-size:16px;">'
        f"{text}</a></div>"
    )


def _fallback_link(url: str) -> str:
    """Kept as a secondary fallback (some email clients strip button
    styling or block images) - word-break so a long URL never gets cut off
    or forces horizontal scrolling on a phone."""
    return (
        '<p style="font-size:12px;color:#94a3b8;margin-top:4px;">'
        "Button not working? Copy and paste this link into your browser:<br>"
        f'<span style="word-break:break-all;">{url}</span></p>'
    )


async def _send(*, to_email: str, subject: str, text_body: str, html_body: str) -> bool:
    if not settings.smtp_username or not settings.smtp_password:
        _logger.info("SMTP not configured - skipping email (%s) to %s", subject, to_email)
        return False

    from_email = settings.smtp_from_email or settings.smtp_username
    message = EmailMessage()
    message["From"] = f"{settings.smtp_from_name} <{from_email}>"
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")

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
        _logger.exception("Failed to send email (%s) to %s", subject, to_email)
        return False


async def send_invite_email(*, to_email: str, farm_name: str, role: str, invited_by_email: str | None) -> bool:
    """Emails a team invite via SMTP (e.g. Gmail + an App Password).

    Best-effort: a failed or unconfigured send must never block creating the
    invitation itself - the invite still works if the person just signs in
    directly with the invited email (see team.py::my_invitations), this is
    only a courtesy notification. Returns whether the email actually went
    out, so the caller can tell the frontend whether to fall back to
    "share this invite directly".
    """
    inviter_line = f" by {invited_by_email}" if invited_by_email else ""
    register_url = f"{settings.app_public_url}/register"

    text_body = (
        f"You've been invited{inviter_line} to join {farm_name} on FlockGuard as a {role}.\n\n"
        f"Sign in or create an account at {register_url} using this email address "
        f"({to_email}) and the invitation will be waiting for you to accept.\n\n"
        "- FlockGuard"
    )
    body_html = f"""
      <h2 style="color:#1B4332;margin:0 0 4px;">You've been invited to FlockGuard</h2>
      <p style="color:#475569;font-size:14px;">
        You've been invited{inviter_line} to join <strong>{farm_name}</strong> as a <strong>{role}</strong>.
      </p>
      {_cta_button("Accept Invitation", register_url)}
      {_fallback_link(register_url)}
      <p style="font-size:13px;color:#475569;margin-top:16px;">
        Sign in or create an account using <strong>{to_email}</strong> to see and accept it.
      </p>
    """
    return await _send(
        to_email=to_email,
        subject=f"You've been invited to join {farm_name} on FlockGuard",
        text_body=text_body,
        html_body=_html_shell(f"Join {farm_name} on FlockGuard", body_html),
    )


async def send_password_reset_email(*, to_email: str, reset_link: str) -> bool:
    """Best-effort, same as send_invite_email - the caller (see
    app/api/routes/auth.py) always returns a generic success response
    regardless of whether this actually sends, so a failure here is never
    visible to whoever's requesting the reset (avoids confirming/denying
    that an email address has an account)."""
    text_body = (
        "We received a request to reset your FlockGuard password.\n\n"
        f"Reset it here: {reset_link}\n\n"
        "If you didn't request this, you can safely ignore this email - your password will stay the same.\n\n"
        "- FlockGuard"
    )
    body_html = f"""
      <h2 style="color:#1B4332;margin:0 0 4px;">Reset your password</h2>
      <p style="color:#475569;font-size:14px;">
        We received a request to reset the password for your FlockGuard account
        (<strong>{to_email}</strong>).
      </p>
      {_cta_button("Reset Password", reset_link)}
      {_fallback_link(reset_link)}
      <p style="font-size:13px;color:#475569;margin-top:16px;">
        If you didn't request this, you can safely ignore this email - your password won't change.
      </p>
    """
    return await _send(
        to_email=to_email,
        subject="Reset your FlockGuard password",
        text_body=text_body,
        html_body=_html_shell("Reset your FlockGuard password", body_html),
    )


async def send_alert_email(
    *, to_emails: list[str], farm_name: str, house_name: str, status: str, score: int, factors: list[str]
) -> bool:
    """Notifies an org's owners/managers (see
    membership_service.get_notification_emails) the moment a NEW alert
    opens for a house - not on every subsequent check while it stays open,
    only its creation (see the call site in flock_checks.py), so this never
    turns into a flood of near-duplicate emails for one ongoing issue."""
    if not to_emails:
        return False

    status_label = status.capitalize()
    status_color = STATUS_COLORS.get(status, "#B3811A")
    alerts_url = f"{settings.app_public_url}/alerts"

    factor_lines = "\n".join(f"- {f}" for f in factors[:5])
    text_body = (
        f"{house_name} on {farm_name} needs a check: risk is now {status_label} ({score} out of 100).\n\n"
        + (f"What we noticed:\n{factor_lines}\n\n" if factor_lines else "")
        + f"Check it here: {alerts_url}\n\n"
        "- FlockGuard"
    )
    factors_html = (
        "<ul style=\"color:#475569;font-size:13px;padding-left:18px;margin:12px 0;\">"
        + "".join(f"<li style='margin-bottom:4px;'>{f}</li>" for f in factors[:5])
        + "</ul>"
        if factors
        else ""
    )
    body_html = f"""
      <span style="display:inline-block;background:{status_color}1A;color:{status_color};font-weight:700;
                    font-size:12px;padding:4px 12px;border-radius:9999px;">
        {status_label}
      </span>
      <h2 style="color:#1B4332;margin:12px 0 4px;">{house_name} needs attention</h2>
      <p style="color:#475569;font-size:14px;">
        Risk is now <strong>{score} out of 100</strong> on <strong>{farm_name}</strong>. Please go and check the birds.
      </p>
      {factors_html}
      {_cta_button("See the warning", alerts_url)}
    """
    html_body = _html_shell(f"{house_name} is at {status_label} risk", body_html)

    # Sent individually (not one message with every recipient in To:) so a
    # bad address for one manager can't affect delivery to the rest, and so
    # no recipient sees the others' email addresses.
    results = []
    for to_email in to_emails:
        results.append(
            await _send(
                to_email=to_email,
                subject=f"{house_name} is at {status_label} risk - FlockGuard",
                text_body=text_body,
                html_body=html_body,
            )
        )
    return any(results)
