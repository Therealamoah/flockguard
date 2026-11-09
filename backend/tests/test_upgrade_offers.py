import pytest
from fastapi.testclient import TestClient

from app.core.firebase import get_current_user
from app.core.firestore import get_firestore_client
from app.main import app
from tests.test_admin import ADMIN, _seed_org

OWNER = {"uid": "org-1", "email": "org-1@farm.test"}
WORKER = {"uid": "org-1-worker", "email": "worker@farm.test", "org_id": "org-1"}


@pytest.fixture
def emails(monkeypatch):
    sent = []

    async def fake_send(**kwargs):
        sent.append(kwargs)
        return True

    monkeypatch.setattr("app.api.routes.admin.send_upgrade_offer_email", fake_send)
    return sent


@pytest.fixture
def as_user(fake_db, monkeypatch):
    def _no_user(*args, **kwargs):
        raise ValueError("no such user")

    monkeypatch.setattr("app.services.admin_service.firebase_auth.get_user", _no_user)
    app.dependency_overrides[get_firestore_client] = lambda: fake_db
    client = TestClient(app)

    def _as(token):
        app.dependency_overrides[get_current_user] = lambda: token
        return client

    yield _as
    app.dependency_overrides.clear()


def _subscription(db, **fields):
    db.collection("organizations").document("org-1").collection("subscription").document("current").set(
        fields, merge=True
    )


def test_offer_emails_owner_and_shows_banner_without_changing_plan(as_user, fake_db, emails):
    _seed_org(fake_db, "org-1")
    res = as_user(ADMIN).post("/admin/orgs/org-1/upgrade-offer", json={"plan": "growth", "message": "Room to grow"})
    assert res.status_code == 200
    assert res.json()["status"] == "open"
    assert res.json()["email_sent"] is True
    assert emails[0]["to_email"] == "org-1@farm.test"
    assert emails[0]["plan"] == "growth" and emails[0]["price_ghs"] == 549
    assert emails[0]["farm_name"] == "Sunrise Farm"

    # The plan itself didn't change - only the farmer's payment does that.
    assert as_user(ADMIN).get("/admin/orgs/org-1").json()["plan"] == "pilot"

    offer = as_user(OWNER).get("/billing/upgrade-offer").json()["offer"]
    assert offer["plan"] == "growth"
    assert offer["message"] == "Room to grow"
    assert offer["limits"]["houses"] == 25

    log = as_user(ADMIN).get("/admin/audit-log").json()
    assert log[0]["action"] == "upgrade.offer"


def test_owner_can_dismiss(as_user, fake_db, emails):
    _seed_org(fake_db, "org-1")
    as_user(ADMIN).post("/admin/orgs/org-1/upgrade-offer", json={"plan": "starter"})
    assert as_user(OWNER).post("/billing/upgrade-offer/dismiss").status_code == 204
    assert as_user(OWNER).get("/billing/upgrade-offer").json()["offer"] is None
    assert as_user(ADMIN).get("/admin/orgs/org-1").json()["upgrade_offer"]["status"] == "dismissed"


def test_offer_counts_as_accepted_once_they_pay(as_user, fake_db, emails):
    _seed_org(fake_db, "org-1")
    as_user(ADMIN).post("/admin/orgs/org-1/upgrade-offer", json={"plan": "growth"})
    _subscription(fake_db, plan="growth", paystack_customer_code="CUS_1")
    assert as_user(OWNER).get("/billing/upgrade-offer").json()["offer"] is None
    assert as_user(ADMIN).get("/admin/orgs/org-1").json()["upgrade_offer"]["status"] == "accepted"


def test_offer_must_be_an_upgrade(as_user, fake_db, emails):
    _seed_org(fake_db, "org-1", plan="growth", price=549)
    res = as_user(ADMIN).post("/admin/orgs/org-1/upgrade-offer", json={"plan": "starter"})
    assert res.status_code == 409
    assert as_user(ADMIN).post("/admin/orgs/org-1/upgrade-offer", json={"plan": "enterprise"}).status_code == 422


def test_withdraw(as_user, fake_db, emails):
    _seed_org(fake_db, "org-1")
    assert as_user(ADMIN).delete("/admin/orgs/org-1/upgrade-offer").status_code == 404
    as_user(ADMIN).post("/admin/orgs/org-1/upgrade-offer", json={"plan": "pro"})
    assert as_user(ADMIN).delete("/admin/orgs/org-1/upgrade-offer").json()["status"] == "withdrawn"
    assert as_user(OWNER).get("/billing/upgrade-offer").json()["offer"] is None


def test_only_owners_see_offers_and_only_admins_make_them(as_user, fake_db, emails):
    _seed_org(fake_db, "org-1")
    assert as_user(OWNER).post("/admin/orgs/org-1/upgrade-offer", json={"plan": "pro"}).status_code == 403
    assert as_user(WORKER).get("/billing/upgrade-offer").status_code == 403


def test_admin_set_paid_plan_is_not_counted_as_revenue(as_user, fake_db):
    """A plan switched on by "Change plan" has no Paystack billing behind it."""
    _seed_org(fake_db, "org-1")
    as_user(ADMIN).patch("/admin/orgs/org-1/subscription", json={"plan": "pro", "reason": "Testing"})
    totals = as_user(ADMIN).get("/admin/overview").json()["totals"]
    assert totals["mrr_ghs"] == 0 and totals["paying_orgs"] == 0
