from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.firebase import get_current_user
from app.core.firestore import get_firestore_client
from app.main import app
from app.services.usage_service import current_period_key

ADMIN = {"uid": "admin-uid", "email": "ops@flockguard.test", "platform_admin": True}


@pytest.fixture
def as_user(fake_db):
    app.dependency_overrides[get_firestore_client] = lambda: fake_db
    client = TestClient(app)

    def _as(token: dict) -> TestClient:
        app.dependency_overrides[get_current_user] = lambda: token
        return client

    yield _as
    app.dependency_overrides.clear()


@pytest.fixture
def firebase_calls(monkeypatch):
    calls = {"update_user": [], "revoked": []}
    monkeypatch.setattr(
        "app.services.admin_service.firebase_auth.update_user",
        lambda uid, **kw: calls["update_user"].append((uid, kw)),
    )
    monkeypatch.setattr(
        "app.services.admin_service.firebase_auth.revoke_refresh_tokens", lambda uid: calls["revoked"].append(uid)
    )

    def _no_user(uid):
        raise ValueError("no such user")

    monkeypatch.setattr("app.services.admin_service.firebase_auth.get_user", _no_user)
    return calls


def _seed_org(db, org_id="org-1", *, plan="pilot", price=0, ai_requests=0):
    now = datetime.now(timezone.utc).isoformat()
    org = db.collection("organizations").document(org_id)
    org.collection("members").document(org_id).set(
        {"email": f"{org_id}@farm.test", "display_name": "Owner", "role": "owner", "status": "active", "joined_at": now}
    )
    org.collection("members").document(f"{org_id}-worker").set(
        {"email": "worker@farm.test", "role": "worker", "status": "active", "joined_at": now}
    )
    farm = org.collection("farms").document("farm-1")
    farm.set({"name": "Sunrise Farm"})
    house = farm.collection("houses").document("house-1")
    house.set({"name": "House A"})
    house.collection("flock_checks").document("c1").set({"recorded_at": now, "risk_score": 20})
    org.collection("alerts").document("a1").set({"status": "critical", "resolved": False, "created_at": now})
    org.collection("subscription").document("current").set(
        {"plan": plan, "status": "active", "price_ghs": price, "limits": {"houses": 5, "ai_requests_monthly": 10},
         "paystack_email_token": "secret-token"}
    )
    org.collection("usage_periods").document(current_period_key()).set({"ai_requests": ai_requests})


def test_non_admin_is_rejected(as_user):
    client = as_user({"uid": "farmer", "email": "farmer@example.com"})
    for path in ("/admin/me", "/admin/overview", "/admin/orgs", "/admin/users", "/admin/ai-usage", "/admin/audit-log"):
        assert client.get(path).status_code == 403


def test_org_owner_claim_is_not_enough(as_user, fake_db):
    _seed_org(fake_db)
    client = as_user({"uid": "org-1", "email": "org-1@farm.test", "platform_admin": "true"})
    assert client.get("/admin/orgs").status_code == 403


def test_overview_aggregates_across_orgs(as_user, fake_db):
    _seed_org(fake_db, "org-1", plan="starter", price=249, ai_requests=9)
    fake_db.collection("organizations").document("org-1").collection("subscription").document("current").set(
        {"paystack_customer_code": "CUS_123"}, merge=True
    )
    _seed_org(fake_db, "org-2")

    data = as_user(ADMIN).get("/admin/overview").json()

    assert data["totals"]["organizations"] == 2
    assert data["totals"]["houses"] == 2
    assert data["totals"]["active_orgs_7d"] == 2
    assert data["totals"]["mrr_ghs"] == 249
    assert data["totals"]["paying_orgs"] == 1
    assert data["totals"]["critical_open_alerts"] == 2
    assert data["plan_distribution"] == {"starter": 1, "pilot": 1}
    assert [o["org_id"] for o in data["near_limit"]] == ["org-1"]
    assert sum(d["count"] for d in data["checks_by_day"]) == 2


def test_org_detail_hides_paystack_secrets(as_user, fake_db, firebase_calls):
    _seed_org(fake_db)
    data = as_user(ADMIN).get("/admin/orgs/org-1").json()

    assert data["owner_email"] == "org-1@farm.test"
    assert data["farms"][0]["houses"][0]["name"] == "House A"
    assert len(data["members"]) == 2
    assert "paystack_email_token" not in data["subscription"]
    assert as_user(ADMIN).get("/admin/orgs/missing").status_code == 404


def test_plan_override_is_comped_and_audited(as_user, fake_db):
    _seed_org(fake_db)
    client = as_user(ADMIN)

    res = client.patch(
        "/admin/orgs/org-1/subscription",
        json={"plan": "growth", "comped": True, "limits": {"houses": 40}, "reason": "Pilot partner"},
    )
    assert res.status_code == 200
    sub = res.json()
    assert sub["plan"] == "growth"
    assert sub["price_ghs"] == 0
    assert sub["limits"]["houses"] == 40
    assert sub["limits"]["birds"] == 50_000

    # Comped plans never count toward MRR.
    assert client.get("/admin/overview").json()["totals"]["mrr_ghs"] == 0

    log = client.get("/admin/audit-log").json()
    assert log[0]["action"] == "subscription.override"
    assert log[0]["reason"] == "Pilot partner"
    assert log[0]["before"]["plan"] == "pilot"


def test_enterprise_override_requires_limits(as_user, fake_db):
    _seed_org(fake_db)
    res = as_user(ADMIN).patch("/admin/orgs/org-1/subscription", json={"plan": "enterprise", "reason": "Deal"})
    assert res.status_code == 422


def test_admin_writes_require_a_reason(as_user, fake_db, firebase_calls):
    _seed_org(fake_db)
    assert as_user(ADMIN).post("/admin/orgs/org-1/suspend", json={}).status_code == 422


def test_suspend_and_reactivate_org(as_user, fake_db, firebase_calls):
    _seed_org(fake_db)
    client = as_user(ADMIN)

    res = client.post("/admin/orgs/org-1/suspend", json={"reason": "Chargeback"})
    assert res.status_code == 200
    assert res.json()["disabled_accounts"] == 2
    assert {uid for uid, kw in firebase_calls["update_user"] if kw == {"disabled": True}} == {"org-1", "org-1-worker"}
    assert set(firebase_calls["revoked"]) == {"org-1", "org-1-worker"}
    assert client.get("/admin/orgs/org-1").json()["platform_status"] == "suspended"
    assert client.post("/admin/orgs/org-1/suspend", json={"reason": "again"}).status_code == 409

    res = client.post("/admin/orgs/org-1/reactivate", json={"reason": "Resolved"})
    assert res.status_code == 200
    assert ("org-1", {"disabled": False}) in firebase_calls["update_user"]
    assert [e["action"] for e in client.get("/admin/audit-log").json()] == ["org.reactivate", "org.suspend"]


def test_user_search_and_disable(as_user, fake_db, firebase_calls):
    _seed_org(fake_db)
    client = as_user(ADMIN)

    users = client.get("/admin/users", params={"q": "WORKER@"}).json()
    assert [u["uid"] for u in users] == ["org-1-worker"]

    assert client.post("/admin/users/org-1-worker/disable", json={"reason": "Abuse"}).status_code == 200
    assert firebase_calls["update_user"] == [("org-1-worker", {"disabled": True})]
    assert client.post("/admin/users/admin-uid/disable", json={"reason": "oops"}).status_code == 400


def test_ai_usage_ranks_orgs(as_user, fake_db):
    _seed_org(fake_db, "org-1", ai_requests=3)
    _seed_org(fake_db, "org-2", ai_requests=8)
    fake_db.collection("organizations").document("org-2").collection("agent_runs").document("r1").set(
        {"status": "completed", "skill": "investigate_flock_risk", "created_at": datetime.now(timezone.utc).isoformat()}
    )

    data = as_user(ADMIN).get("/admin/ai-usage").json()
    assert data["total_requests_month"] == 11
    assert [o["org_id"] for o in data["orgs"]] == ["org-2", "org-1"]
    assert data["orgs"][0]["agent_runs_month"] == 1
    assert data["agent_runs_by_skill"] == {"investigate_flock_risk": 1}
