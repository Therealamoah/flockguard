from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.firebase import get_current_user
from app.core.firestore import get_firestore_client
from app.main import app
from app.services import activity_service
from tests.test_admin import ADMIN, _seed_org

OWNER = {"uid": "org-1", "email": "org-1@farm.test", "name": "Ama"}
WORKER = {"uid": "org-1-worker", "email": "worker@farm.test", "org_id": "org-1"}


@pytest.fixture(autouse=True)
def _fresh_throttle():
    activity_service.reset_throttle()
    yield
    activity_service.reset_throttle()


@pytest.fixture
def as_user(fake_db, monkeypatch):
    def _no_user(uid):
        raise ValueError("no such user")

    monkeypatch.setattr("app.services.admin_service.firebase_auth.get_user", _no_user)
    app.dependency_overrides[get_firestore_client] = lambda: fake_db
    client = TestClient(app)

    def _as(token: dict) -> TestClient:
        app.dependency_overrides[get_current_user] = lambda: token
        return client

    yield _as
    app.dependency_overrides.clear()


# --- heartbeat / activity -----------------------------------------------------


def test_heartbeat_records_last_seen_and_day(as_user, fake_db):
    res = as_user(OWNER).post("/activity/heartbeat", json={"path": "/houses"})
    assert res.status_code == 204
    row = fake_db.collection("user_activity").document("org-1").get().to_dict()
    assert row["org_id"] == "org-1"
    assert row["last_path"] == "/houses"
    assert row["display_name"] == "Ama"
    assert row["active_days"] == [datetime.now(timezone.utc).date().isoformat()]
    assert row["first_seen_at"]


def test_heartbeat_is_throttled_but_new_day_always_writes(fake_db):
    day1 = datetime(2026, 11, 1, 10, 0, tzinfo=timezone.utc)
    assert activity_service.record_heartbeat(fake_db, OWNER, now=day1)
    assert not activity_service.record_heartbeat(fake_db, OWNER, now=day1 + timedelta(seconds=30))
    assert activity_service.record_heartbeat(fake_db, OWNER, now=day1 + timedelta(minutes=3))
    # Just past midnight UTC: written even inside the throttle window.
    late = datetime(2026, 11, 1, 23, 59, 30, tzinfo=timezone.utc)
    activity_service.record_heartbeat(fake_db, OWNER, now=late)
    assert activity_service.record_heartbeat(fake_db, OWNER, now=late + timedelta(seconds=40))

    row = fake_db.collection("user_activity").document("org-1").get().to_dict()
    assert row["active_days"] == ["2026-11-01", "2026-11-02"]
    assert row["first_seen_at"] == day1.isoformat()


def test_heartbeat_requires_auth(client):
    assert client.post("/activity/heartbeat", json={}).status_code == 401


def test_admin_activity_counts_online_dau_mau_and_dormant(as_user, fake_db):
    _seed_org(fake_db, "org-1")
    now = datetime.now(timezone.utc)
    activity_service.record_heartbeat(fake_db, OWNER, now=now)
    # Worker was last active 20 days ago: counts toward MAU, and is dormant.
    activity_service.record_heartbeat(fake_db, WORKER, now=now - timedelta(days=20))

    data = as_user(ADMIN).get("/admin/activity").json()
    t = data["totals"]
    assert t["online_now"] == 1
    assert t["dau"] == 1
    assert t["wau"] == 1
    assert t["mau"] == 2
    assert t["stickiness"] == 0.5
    assert [p["uid"] for p in data["online"]] == ["org-1"]
    assert data["online"][0]["farm_name"] == "Sunrise Farm"
    assert [p["uid"] for p in data["dormant"]] == ["org-1-worker"]
    assert data["dau_by_day"][-1]["count"] == 1
    assert len(data["dau_by_day"]) == 30


def test_admin_activity_is_admin_only(as_user):
    assert as_user(OWNER).get("/admin/activity").status_code == 403


def test_user_search_includes_last_active(as_user, fake_db):
    _seed_org(fake_db, "org-1")
    activity_service.record_heartbeat(fake_db, OWNER)
    users = {u["uid"]: u for u in as_user(ADMIN).get("/admin/users").json()}
    assert users["org-1"]["last_seen_at"]
    assert users["org-1"]["days_active_30d"] == 1
    assert users["org-1-worker"]["last_seen_at"] is None


def test_org_detail_shows_member_last_active(as_user, fake_db):
    _seed_org(fake_db, "org-1")
    activity_service.record_heartbeat(fake_db, OWNER)
    members = {m["id"]: m for m in as_user(ADMIN).get("/admin/orgs/org-1").json()["members"]}
    assert members["org-1"]["last_seen_at"]
    assert members["org-1-worker"]["last_seen_at"] is None


# --- enterprise ---------------------------------------------------------------


def _request(client, **overrides):
    body = {
        "houses": 60,
        "birds": 120000,
        "phone": "+233 20 000 0000",
        "contact_method": "whatsapp",
        "message": "We run 3 sites",
    }
    return client.post("/billing/enterprise-request", json={**body, **overrides})


def test_owner_can_request_enterprise_once(as_user, fake_db):
    _seed_org(fake_db, "org-1", plan="pro", price=999)
    client = as_user(OWNER)
    assert client.get("/billing/enterprise-request").json() == {"request": None}

    res = _request(client)
    assert res.status_code == 201
    assert res.json()["created"] is True
    assert res.json()["request"]["status"] == "new"

    again = _request(client)
    assert again.json()["created"] is False
    assert again.json()["request"]["id"] == res.json()["request"]["id"]
    assert client.get("/billing/enterprise-request").json()["request"]["id"] == res.json()["request"]["id"]

    stored = list(fake_db.collection("enterprise_requests").stream())
    assert len(stored) == 1
    lead = stored[0].to_dict()
    assert lead["farm_name"] == "Sunrise Farm"
    assert lead["current_plan"] == "pro"
    assert lead["usage"]["houses"] == 1
    assert lead["requested"] == {"houses": 60, "birds": 120000}


def test_workers_cannot_request_enterprise(as_user, fake_db):
    _seed_org(fake_db, "org-1")
    assert _request(as_user(WORKER)).status_code == 403


def test_enterprise_request_emails_sales_when_configured(as_user, fake_db, monkeypatch):
    from app.core.config import settings

    sent = []

    async def fake_send(**kwargs):
        sent.append(kwargs)
        return True

    monkeypatch.setattr(settings, "sales_notification_email", "sales@flockguard.test")
    monkeypatch.setattr("app.api.routes.billing.send_enterprise_request_email", fake_send)
    _seed_org(fake_db, "org-1")
    _request(as_user(OWNER))
    assert sent and sent[0]["to_email"] == "sales@flockguard.test"
    assert sent[0]["admin_url"].endswith("/admin/enterprise")


def test_admin_sees_leads_and_moves_them_through_the_pipeline(as_user, fake_db):
    _seed_org(fake_db, "org-1", plan="pro", price=999)
    request_id = _request(as_user(OWNER)).json()["request"]["id"]
    admin = as_user(ADMIN)

    data = admin.get("/admin/enterprise").json()
    assert data["counts"]["new"] == 1
    assert data["leads"][0]["email"] == "org-1@farm.test"
    assert data["candidates"][0]["org_id"] == "org-1"
    assert data["candidates"][0]["reasons"][0] == "asked for Enterprise"

    res = admin.patch(f"/admin/enterprise/{request_id}", json={"status": "contacted", "note": "Called, wants 60 houses"})
    assert res.status_code == 200
    assert res.json()["status"] == "contacted"
    assert res.json()["notes"][0]["by"] == ADMIN["email"]

    log = admin.get("/admin/audit-log").json()
    assert log[0]["action"] == "enterprise.status"
    assert log[0]["after"] == {"status": "contacted"}

    # A note on its own doesn't add an audit entry.
    admin.patch(f"/admin/enterprise/{request_id}", json={"note": "Sent proposal"})
    assert len(admin.get("/admin/audit-log").json()) == 1
    assert admin.patch(f"/admin/enterprise/{request_id}", json={}).status_code == 422
    assert admin.patch("/admin/enterprise/missing", json={"status": "won"}).status_code == 404

    # Closing the lead lets the org send a new request later.
    admin.patch(f"/admin/enterprise/{request_id}", json={"status": "won"})
    assert as_user(OWNER).get("/billing/enterprise-request").json()["request"] is None


def test_upgrade_candidates_flag_orgs_near_limits(as_user, fake_db):
    _seed_org(fake_db, "org-1", plan="pro", price=999, ai_requests=9)  # 90% of its 10-request limit
    _seed_org(fake_db, "org-2", plan="pilot")
    candidates = as_user(ADMIN).get("/admin/enterprise").json()["candidates"]
    assert [c["org_id"] for c in candidates] == ["org-1"]
    assert "90% of AI requests limit" in candidates[0]["reasons"]


def test_enterprise_admin_routes_are_admin_only(as_user):
    client = as_user(OWNER)
    assert client.get("/admin/enterprise").status_code == 403
    assert client.patch("/admin/enterprise/x", json={"status": "won"}).status_code == 403
