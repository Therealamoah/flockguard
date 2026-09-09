from fastapi.testclient import TestClient

from app.core.firebase import get_current_user
from app.core.firestore import get_firestore_client
from app.main import app
from tests.fake_firestore import FakeFirestoreClient


def test_unauthenticated_request_to_protected_route_is_rejected(client):
    response = client.get("/farms")
    assert response.status_code == 401


def test_unauthenticated_flock_check_submission_is_rejected(client):
    response = client.post("/farms/f1/houses/h1/flock-checks", json={"period": "morning", "bird_count": 100})
    assert response.status_code == 401


def test_debug_route_requires_auth(client):
    response = client.get("/debug")
    assert response.status_code == 401


def test_debug_route_disabled_in_production(authed_client, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "environment", "production")
    response = authed_client.get("/debug")
    assert response.status_code == 404


def test_debug_route_available_outside_production(authed_client):
    response = authed_client.get("/debug")
    assert response.status_code == 200
    body = response.json()
    assert "grok_api_key" not in str(body)  # never leaks the secret itself


def test_cross_org_access_never_sees_another_orgs_data():
    """Two different Firebase users (no shared org_id claim) each get an
    isolated org (get_current_org_id falls back to uid). Farm A, created by
    user A, must never appear in user B's /farms listing - even though both
    hit the exact same endpoint with the exact same Firestore instance.
    """
    fake_db = FakeFirestoreClient()
    app.dependency_overrides[get_firestore_client] = lambda: fake_db

    try:
        app.dependency_overrides[get_current_user] = lambda: {"uid": "user-a"}
        with TestClient(app) as client_a:
            created = client_a.post("/farms", json={"name": "User A's Farm"})
            assert created.status_code == 201

        app.dependency_overrides[get_current_user] = lambda: {"uid": "user-b"}
        with TestClient(app) as client_b:
            listing = client_b.get("/farms")
            assert listing.status_code == 200
            assert listing.json() == []  # never sees user A's farm
    finally:
        app.dependency_overrides.clear()
