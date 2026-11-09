from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.firebase import get_current_user
from app.core.firestore import get_firestore_client
from app.main import app
from tests.test_admin import ADMIN, _seed_org


@pytest.fixture
def admin(fake_db, monkeypatch):
    def _no_user(*args, **kwargs):
        raise ValueError("no such user")

    monkeypatch.setattr("app.services.admin_service.firebase_auth.get_users", _no_user)
    app.dependency_overrides[get_firestore_client] = lambda: fake_db
    app.dependency_overrides[get_current_user] = lambda: ADMIN
    yield TestClient(app)
    app.dependency_overrides.clear()


def _iso(delta=timedelta()):
    return (datetime.now(timezone.utc) - delta).isoformat()


def _owner_only(db, org_id, *, joined_ago):
    db.collection("organizations").document(org_id).collection("members").document(org_id).set(
        {"email": f"{org_id}@farm.test", "role": "owner", "status": "active", "joined_at": _iso(joined_ago)}
    )


def _set_check_age(db, org_id, age):
    house = (db.collection("organizations").document(org_id).collection("farms").document("farm-1")
             .collection("houses").document("house-1"))
    house.collection("flock_checks").document("c1").set({"recorded_at": _iso(age), "risk_score": 10})


def _resolve_alerts(db, org_id):
    db.collection("organizations").document(org_id).collection("alerts").document("a1").set(
        {"status": "critical", "resolved": True, "created_at": _iso()}
    )


def test_farmer_stages(admin, fake_db):
    _seed_org(fake_db, "healthy")          # checked today, but has a critical alert -> health risk
    _seed_org(fake_db, "active")
    _resolve_alerts(fake_db, "active")
    _seed_org(fake_db, "slipping")
    _resolve_alerts(fake_db, "slipping")
    _set_check_age(fake_db, "slipping", timedelta(days=10))
    _seed_org(fake_db, "quiet")
    _resolve_alerts(fake_db, "quiet")
    _set_check_age(fake_db, "quiet", timedelta(days=40))
    _owner_only(fake_db, "newbie", joined_ago=timedelta(days=5))
    _seed_org(fake_db, "late-payer")
    _resolve_alerts(fake_db, "late-payer")
    fake_db.collection("organizations").document("late-payer").collection("subscription").document("current").set(
        {"plan": "starter", "status": "past_due"}, merge=True
    )

    data = admin.get("/admin/briefing").json()
    stages = {f["org_id"]: f["stage"] for f in data["farmers"]}
    assert stages == {
        "healthy": "health_risk",
        "active": "active",
        "slipping": "slipping",
        "quiet": "inactive",
        "newbie": "setting_up",
        "late-payer": "payment_issue",
    }
    assert data["farmers"][0]["stage"] == "payment_issue"  # most urgent first
    assert data["stage_counts"]["active"] == 1

    kinds = {(i["kind"], i["org_id"]) for i in data["attention"]}
    assert ("payment", "late-payer") in kinds
    assert ("stuck_setup", "newbie") in kinds
    assert ("quiet", "slipping") in kinds and ("quiet", "quiet") in kinds
    assert data["attention"][0]["severity"] == "critical"


def test_stale_critical_alert_and_enterprise_and_limits(admin, fake_db):
    _seed_org(fake_db, "org-1", plan="pro", ai_requests=10)  # 100% of a 10-request limit
    fake_db.collection("organizations").document("org-1").collection("alerts").document("a1").set(
        {"status": "critical", "resolved": False, "created_at": _iso(timedelta(hours=30))}
    )
    fake_db.collection("enterprise_requests").document("r1").set(
        {"org_id": "org-1", "status": "new", "farm_name": "Sunrise Farm", "requested": {"houses": 40},
         "created_at": _iso()}
    )

    items = admin.get("/admin/briefing").json()["attention"]
    by_kind = {i["kind"]: i for i in items}
    assert by_kind["stale_critical"]["title"].startswith("Critical alert unresolved for 30h")
    assert by_kind["enterprise"]["link"] == "/admin/enterprise"
    assert "40 houses" in by_kind["enterprise"]["detail"]
    assert by_kind["limit"]["title"] == "Hit a plan limit"


def test_week_over_week(admin, fake_db):
    _seed_org(fake_db, "org-1")  # one check today, one alert today, joined today
    data = admin.get("/admin/briefing").json()["week"]
    assert data["flock_checks"] == {"this_week": 1, "last_week": 0}
    assert data["alerts_raised"]["this_week"] == 1
    assert data["signups"]["this_week"] == 1


def test_briefing_is_admin_only(fake_db):
    app.dependency_overrides[get_firestore_client] = lambda: fake_db
    app.dependency_overrides[get_current_user] = lambda: {"uid": "farmer", "email": "f@x.test"}
    try:
        assert TestClient(app).get("/admin/briefing").status_code == 403
    finally:
        app.dependency_overrides.clear()
