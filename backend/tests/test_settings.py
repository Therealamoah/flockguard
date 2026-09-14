from datetime import datetime, timezone

from app.core.refs import members_ref
from tests.conftest import FAKE_UID

OWNER_UID = "owner-1"
OWNER_EMAIL = "owner@example.com"


def _seed_member(fake_db, org_id, uid, email, role):
    members_ref(fake_db, org_id).document(uid).set(
        {
            "user_id": uid,
            "email": email,
            "display_name": email,
            "role": role,
            "status": "active",
            "joined_at": datetime.now(timezone.utc).isoformat(),
            "invited_by": org_id,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    )


def test_owner_can_update_farm_settings(authed_client):
    farm = authed_client.post("/farms", json={"name": "Mr Amoah Farm"}).json()
    response = authed_client.patch(
        "/settings",
        params={"farm_id": farm["id"]},
        json={"timezone": "Africa/Accra", "country": "Ghana", "temperature_unit": "celsius"},
    )
    assert response.status_code == 200

    got = authed_client.get("/settings", params={"farm_id": farm["id"]}).json()
    assert got["timezone"] == "Africa/Accra"
    assert got["country"] == "Ghana"


def test_timezone_persists_and_is_read_back(authed_client):
    farm = authed_client.post("/farms", json={"name": "Farm"}).json()
    authed_client.patch("/settings", params={"farm_id": farm["id"]}, json={"timezone": "America/New_York"})
    got = authed_client.get("/settings", params={"farm_id": farm["id"]}).json()
    assert got["timezone"] == "America/New_York"


def test_invalid_timezone_rejected(authed_client):
    farm = authed_client.post("/farms", json={"name": "Farm"}).json()
    response = authed_client.patch("/settings", params={"farm_id": farm["id"]}, json={"timezone": "Not/ARealZone"})
    assert response.status_code == 422


def test_missing_timezone_falls_back_to_defaults(authed_client):
    farm = authed_client.post("/farms", json={"name": "Farm"}).json()
    got = authed_client.get("/settings", params={"farm_id": farm["id"]}).json()
    assert got["timezone"] is None
    assert got["temperature_unit"] == "celsius"
    assert got["weight_unit"] == "kg"
    assert got["morning_check_start"] == "06:00"
    assert got["morning_check_end"] == "10:00"
    assert got["risk_method"]["configurable"] is False


def test_check_schedule_and_notification_preferences_persist(authed_client):
    farm = authed_client.post("/farms", json={"name": "Farm"}).json()
    authed_client.patch(
        "/settings",
        params={"farm_id": farm["id"]},
        json={
            "morning_check_start": "05:30",
            "morning_check_end": "09:00",
            "notification_preferences": {
                "critical_alerts": True,
                "warning_alerts": False,
                "watch_alerts": False,
                "morning_check_reminder": True,
                "evening_check_reminder": False,
                "daily_farm_brief": True,
                "channels": {"in_app": True, "push": False, "email": False, "whatsapp": "coming_soon", "sms": "coming_soon"},
            },
        },
    )
    got = authed_client.get("/settings", params={"farm_id": farm["id"]}).json()
    assert got["morning_check_start"] == "05:30"
    assert got["notification_preferences"]["warning_alerts"] is False
    assert got["notification_preferences"]["channels"]["push"] is False  # never silently "on"


def test_worker_cannot_modify_settings(make_client, fake_db):
    owner = make_client(OWNER_UID, OWNER_EMAIL)
    owner.get("/team")  # backfill owner membership
    farm = owner.post("/farms", json={"name": "Farm"}).json()
    _seed_member(fake_db, OWNER_UID, "worker-1", "worker@example.com", "worker")

    worker = make_client("worker-1", "worker@example.com", org_id=OWNER_UID)
    response = worker.patch("/settings", params={"farm_id": farm["id"]}, json={"timezone": "Africa/Accra"})
    assert response.status_code == 403

    # Reading settings is fine for any active member, though.
    assert worker.get("/settings", params={"farm_id": farm["id"]}).status_code == 200


def test_manager_can_modify_settings(make_client, fake_db):
    owner = make_client(OWNER_UID, OWNER_EMAIL)
    owner.get("/team")
    farm = owner.post("/farms", json={"name": "Farm"}).json()
    _seed_member(fake_db, OWNER_UID, "manager-1", "manager@example.com", "manager")

    manager = make_client("manager-1", "manager@example.com", org_id=OWNER_UID)
    response = manager.patch("/settings", params={"farm_id": farm["id"]}, json={"timezone": "Africa/Accra"})
    assert response.status_code == 200


def test_account_display_name_update(authed_client, monkeypatch):
    calls = []
    monkeypatch.setattr(
        "app.api.routes.settings.firebase_auth.update_user",
        lambda uid, display_name: calls.append((uid, display_name)),
    )
    response = authed_client.patch("/settings/account", json={"display_name": "Collins Amoah"})
    assert response.status_code == 200
    assert calls == [(FAKE_UID, "Collins Amoah")]


def test_archive_farm(authed_client):
    farm = authed_client.post("/farms", json={"name": "Farm"}).json()
    response = authed_client.post(f"/settings/farms/{farm['id']}/archive")
    assert response.status_code == 200
    got = authed_client.get("/settings", params={"farm_id": farm["id"]}).json()
    assert got["archived"] is True

    response = authed_client.post(f"/settings/farms/{farm['id']}/unarchive")
    assert response.status_code == 200
    got = authed_client.get("/settings", params={"farm_id": farm["id"]}).json()
    assert got["archived"] is False


def test_worker_cannot_archive_farm(make_client, fake_db):
    owner = make_client(OWNER_UID, OWNER_EMAIL)
    owner.get("/team")
    farm = owner.post("/farms", json={"name": "Farm"}).json()
    _seed_member(fake_db, OWNER_UID, "worker-1", "worker@example.com", "worker")

    worker = make_client("worker-1", "worker@example.com", org_id=OWNER_UID)
    assert worker.post(f"/settings/farms/{farm['id']}/archive").status_code == 403


def test_delete_farm_requires_correct_confirmation(authed_client):
    farm = authed_client.post("/farms", json={"name": "My Farm"}).json()
    response = authed_client.post(f"/settings/farms/{farm['id']}/delete", json={"confirmation": "wrong text"})
    assert response.status_code == 400


def test_delete_farm_is_guarded_even_with_correct_confirmation(authed_client):
    """Permanent delete is intentionally disabled until safe cascade delete
    exists - correct confirmation still doesn't perform a real delete."""
    farm = authed_client.post("/farms", json={"name": "My Farm"}).json()
    response = authed_client.post(f"/settings/farms/{farm['id']}/delete", json={"confirmation": "DELETE"})
    assert response.status_code == 501

    # The farm must still exist - nothing was actually deleted.
    assert authed_client.get("/settings", params={"farm_id": farm["id"]}).status_code == 200
