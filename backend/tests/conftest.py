import os

os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("FIREBASE_PROJECT_ID", "test-project")

import pytest
from fastapi.testclient import TestClient

from app.core.firebase import get_current_user
from app.core.firestore import get_firestore_client
from app.main import app
from tests.fake_firestore import FakeFirestoreClient

FAKE_UID = "test-uid-1"


@pytest.fixture
def fake_db():
    return FakeFirestoreClient()


@pytest.fixture
def authed_client(fake_db):
    """A TestClient authenticated as a single fake user, backed by an
    in-memory Firestore. No real Firebase token or GCP credentials involved -
    both `get_current_user` and `get_firestore_client` are overridden.
    """
    app.dependency_overrides[get_current_user] = lambda: {"uid": FAKE_UID, "email": "farmer@example.com"}
    app.dependency_overrides[get_firestore_client] = lambda: fake_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    """An unauthenticated TestClient - no dependency overrides at all - for
    testing that protected routes actually reject unauthenticated callers.
    """
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
