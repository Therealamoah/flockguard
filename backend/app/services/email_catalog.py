"""Every email FlockGuard sends, described for the admin console's Emails
page (GET /admin/emails): when it goes out, who receives it, whether it can
go out right now, and a preview rendered by the exact same build_* function
the real send uses (app/services/email_service.py) - so the preview can't
drift from what people actually receive.
"""

from google.cloud.firestore import Client

from app.core.config import settings
from app.services import email_service
from app.services.notification_service import alert_email_enabled

SAMPLE_FARM = "Sunrise Farm"
SAMPLE_EMAIL = "farmer@example.com"


def _sample_enterprise_request() -> dict:
    return {
        "org_id": "sample-org",
        "display_name": "Ama Mensah",
        "email": SAMPLE_EMAIL,
        "farm_name": SAMPLE_FARM,
        "phone": "+233 20 000 0000",
        "contact_method": "whatsapp",
        "current_plan": "pro",
        "usage": {"houses": 9, "birds": 18000, "team_members": 4},
        "requested": {"houses": 40, "birds": 80000},
        "message": "We're opening two more sites next year.",
    }


# key -> (name, when it's sent, who gets it, sample builder)
TEMPLATES = {
    "password_reset": {
        "name": "Password reset",
        "trigger": "Someone clicks “Forgot password” on the login page.",
        "audience": "The person who asked - only if an account exists for that email.",
        "build": lambda to: email_service.build_password_reset_email(
            to_email=to, reset_link=f"{settings.app_public_url}/reset-password?oobCode=SAMPLE"
        ),
    },
    "team_invite": {
        "name": "Team invite",
        "trigger": "An owner invites someone from the Team page.",
        "audience": "The invited person.",
        "build": lambda to: email_service.build_invite_email(
            to_email=to, farm_name=SAMPLE_FARM, role="manager", invited_by_email="owner@example.com"
        ),
    },
    "alert_critical": {
        "name": "Health alert - critical",
        "trigger": "A flock check opens a NEW critical alert for a house (not repeated while it stays open).",
        "audience": "The farm's active owners and managers - if the farm has turned on email alerts.",
        "build": lambda to: email_service.build_alert_email(
            farm_name=SAMPLE_FARM, house_name="House A", status="critical", score=82,
            factors=["Mortality well above this house's normal", "Birds lethargic", "Unusual sounds (coughing)"],
        ),
    },
    "alert_warning": {
        "name": "Health alert - warning",
        "trigger": "A flock check opens a NEW warning alert for a house.",
        "audience": "The farm's active owners and managers - if the farm has turned on email alerts.",
        "build": lambda to: email_service.build_alert_email(
            farm_name=SAMPLE_FARM, house_name="House B", status="warning", score=58,
            factors=["Feed intake down 25% on yesterday", "Water lower than usual"],
        ),
    },
    "upgrade_offer": {
        "name": "Upgrade offer",
        "trigger": "An admin clicks “Offer upgrade” on an organization's page.",
        "audience": "That organization's owner.",
        "build": lambda to: email_service.build_upgrade_offer_email(
            farm_name=SAMPLE_FARM, plan="growth", price_ghs=549,
            limits={"houses": 25, "birds": 50000, "team_members": 15, "ai_requests_monthly": 3000},
            message="You're at 9 of 10 houses - Growth gives you room for the new site.",
        ),
    },
    "enterprise_request": {
        "name": "Enterprise request (internal)",
        "trigger": "An owner sends the “Request Enterprise” form on the Billing page.",
        "audience": "Your sales inbox (SALES_NOTIFICATION_EMAIL) - never customers.",
        "build": lambda to: email_service.build_enterprise_request_email(
            request=_sample_enterprise_request(), admin_url=f"{settings.app_public_url}/admin/enterprise"
        ),
    },
}


def _alert_email_farms(db: Client) -> tuple[int, int]:
    """(farms with critical-alert emails on, all active farms)."""
    on = total = 0
    for snap in db.collection_group("farms").stream():
        farm = snap.to_dict()
        if farm.get("archived"):
            continue
        total += 1
        if alert_email_enabled(farm, "critical"):
            on += 1
    return on, total


def build_catalog(db: Client) -> dict:
    delivery = email_service.delivery_status()
    farms_on, farms_total = _alert_email_farms(db)

    def status_for(key: str) -> tuple[str, str]:
        if not delivery["configured"]:
            return "off", "Email sending isn't configured (SMTP_USERNAME / SMTP_PASSWORD)."
        if key.startswith("alert_"):
            if farms_on == 0:
                return "limited", (
                    f"Working, but none of the {farms_total} farms has turned on email alerts yet "
                    "(Settings → Notifications → Email)."
                )
            return "on", f"Going out for {farms_on} of {farms_total} farms (the rest have email alerts off)."
        if key == "enterprise_request" and not delivery["sales_notification_email"]:
            return "off", "Set SALES_NOTIFICATION_EMAIL to receive these. Requests still appear in Admin → Enterprise."
        return "on", "Going out whenever it's triggered."

    templates = []
    for key, t in TEMPLATES.items():
        content = t["build"](SAMPLE_EMAIL)
        status, status_note = status_for(key)
        templates.append(
            {
                "key": key,
                "name": t["name"],
                "trigger": t["trigger"],
                "audience": t["audience"],
                "status": status,
                "status_note": status_note,
                "subject": content.subject,
                "text_body": content.text_body,
                "html_body": content.html_body,
            }
        )
    return {
        "delivery": delivery,
        "alert_email_farms": {"enabled": farms_on, "total": farms_total},
        "templates": templates,
    }


async def send_test(key: str, to_email: str) -> bool:
    content = TEMPLATES[key]["build"](to_email)
    return await email_service._send(
        to_email=to_email,
        subject=f"[TEST] {content.subject}",
        text_body=content.text_body,
        html_body=content.html_body,
    )
