import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.firebase import get_current_user
from app.core.firestore import get_firestore_client
from app.main import app
from app.services import email_service
from tests.test_admin import ADMIN


@pytest.fixture
def client_as(fake_db):
    app.dependency_overrides[get_firestore_client] = lambda: fake_db
    client = TestClient(app)

    def _as(token):
        app.dependency_overrides[get_current_user] = lambda: token
        return client

    yield _as
    app.dependency_overrides.clear()


@pytest.fixture
def smtp_on(monkeypatch):
    monkeypatch.setattr(settings, "smtp_username", "login@smtp-brevo.com")
    monkeypatch.setattr(settings, "smtp_password", "secret-key")
    monkeypatch.setattr(settings, "smtp_host", "smtp-relay.brevo.com")
    monkeypatch.setattr(settings, "sales_notification_email", "")


def _farm(db, org, farm_id, *, email_on):
    db.collection("organizations").document(org).collection("farms").document(farm_id).set(
        {"name": farm_id, "notification_preferences": {"channels": {"email": email_on}}}
    )


def test_catalog_lists_every_email_with_previews(client_as, fake_db, smtp_on):
    _farm(fake_db, "org-1", "farm-a", email_on=True)
    _farm(fake_db, "org-2", "farm-b", email_on=False)

    data = client_as(ADMIN).get("/admin/emails").json()
    templates = {t["key"]: t for t in data["templates"]}

    assert set(templates) == {
        "password_reset", "team_invite", "alert_critical", "alert_warning", "upgrade_offer", "enterprise_request",
    }
    assert data["delivery"]["provider"] == "Brevo"
    assert "secret-key" not in str(data)  # the SMTP key never reaches the browser
    assert data["alert_email_farms"] == {"enabled": 1, "total": 2}

    assert templates["password_reset"]["status"] == "on"
    assert templates["alert_critical"]["status"] == "on"
    assert "1 of 2 farms" in templates["alert_critical"]["status_note"]
    assert templates["enterprise_request"]["status"] == "off"
    assert templates["team_invite"]["subject"] == "You've been invited to join Sunrise Farm on FlockGuard"
    assert "Accept Invitation" in templates["team_invite"]["html_body"]


def test_alert_emails_flagged_when_no_farm_has_them_on(client_as, fake_db, smtp_on):
    _farm(fake_db, "org-1", "farm-a", email_on=False)
    templates = {t["key"]: t for t in client_as(ADMIN).get("/admin/emails").json()["templates"]}
    assert templates["alert_warning"]["status"] == "limited"


def test_catalog_reports_smtp_off(client_as, monkeypatch):
    monkeypatch.setattr(settings, "smtp_username", "")
    monkeypatch.setattr(settings, "smtp_password", "")
    data = client_as(ADMIN).get("/admin/emails").json()
    assert data["delivery"]["configured"] is False
    assert {t["status"] for t in data["templates"]} == {"off"}


def test_preview_matches_the_real_send(monkeypatch, smtp_on):
    """The catalog renders through the same builder the real send uses."""
    sent = []

    async def fake_send(**kwargs):
        sent.append(kwargs)
        return True

    monkeypatch.setattr(email_service, "_send", fake_send)
    import asyncio

    asyncio.run(email_service.send_alert_email(
        to_emails=["a@x.test"], farm_name="F", house_name="H", status="critical", score=80, factors=["x"]
    ))
    built = email_service.build_alert_email(farm_name="F", house_name="H", status="critical", score=80, factors=["x"])
    assert sent[0]["html_body"] == built.html_body
    assert sent[0]["subject"] == built.subject


def test_send_test_goes_only_to_the_admin(client_as, monkeypatch, smtp_on):
    sent = []

    async def fake_send(**kwargs):
        sent.append(kwargs)
        return True

    monkeypatch.setattr(email_service, "_send", fake_send)
    res = client_as(ADMIN).post("/admin/emails/alert_critical/test")
    assert res.status_code == 200
    assert res.json() == {"sent": True, "to": ADMIN["email"]}
    assert sent[0]["to_email"] == ADMIN["email"]
    assert sent[0]["subject"].startswith("[TEST] ")

    assert client_as(ADMIN).post("/admin/emails/nope/test").status_code == 404


def test_send_test_reports_failure(client_as, monkeypatch, smtp_on):
    async def failing_send(**kwargs):
        return False

    monkeypatch.setattr(email_service, "_send", failing_send)
    assert client_as(ADMIN).post("/admin/emails/password_reset/test").status_code == 502


def test_email_admin_routes_are_admin_only(client_as):
    farmer = client_as({"uid": "farmer", "email": "f@x.test"})
    assert farmer.get("/admin/emails").status_code == 403
    assert farmer.post("/admin/emails/password_reset/test").status_code == 403
