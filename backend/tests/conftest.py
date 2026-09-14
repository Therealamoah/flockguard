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


@pytest.fixture(autouse=True)
def _no_real_ai_calls_by_default(monkeypatch):
    """Safety net, applied to every test automatically: nothing in this
    suite should ever reach a real Grok/OpenRouter network call. This
    matters more than it used to now that Warning/Critical Flock Check
    submissions schedule a background agent investigation (see
    app/agent/event_handlers.py) - without this, submitting one in a test
    would trigger a real, slow, flaky outbound HTTP call. Tests that want
    to exercise successful AI behavior explicitly monkeypatch
    grok_service.chat / chat_completion themselves, which overrides this
    default within that test (a test's own monkeypatch.setattr always
    wins over this fixture's, since it runs after fixture setup).
    """

    async def _fail_fast(*args, **kwargs):
        raise RuntimeError("Real Grok/OpenRouter calls are not allowed in tests - mock grok_service explicitly.")

    monkeypatch.setattr("app.services.grok_service.grok_service.chat", _fail_fast)
    monkeypatch.setattr("app.services.grok_service.grok_service.chat_completion", _fail_fast)


@pytest.fixture(autouse=True)
def _no_real_emails_by_default(monkeypatch):
    """Same idea as _no_real_ai_calls_by_default above, for SMTP: a
    developer's local .env may have real Gmail credentials configured (see
    app/services/email_service.py) for actually trying the feature by hand,
    but the test suite must never send a real email or make a real network
    call regardless of what's in that .env. Tests that want to assert on
    email-sending behavior explicitly monkeypatch send_invite_email
    themselves, which overrides this default within that test.
    """

    async def _fail_fast(*args, **kwargs):
        raise RuntimeError("Real SMTP sends are not allowed in tests - mock send_invite_email explicitly.")

    monkeypatch.setattr("app.services.email_service.aiosmtplib.send", _fail_fast)


@pytest.fixture(autouse=True)
def _no_real_paystack_config_by_default(monkeypatch):
    """Same idea again, for Paystack: a developer's local .env may have
    real (test-mode) Paystack keys and Plan codes configured (see
    app/services/paystack_service.py) for trying checkout by hand, but
    billing tests assert specific behavior for "not configured yet" states
    (e.g. payments_active is False, checkout returns 503 for a plan with no
    code) that must hold regardless of what's in that .env. Blanked here so
    every test starts from the same clean slate; a test that wants a key or
    plan code present sets it explicitly via monkeypatch, which overrides
    this default within that test."""
    from app.core.config import settings

    for field in (
        "paystack_secret_key",
        "paystack_public_key",
        "paystack_plan_code_starter",
        "paystack_plan_code_growth",
        "paystack_plan_code_pro",
    ):
        monkeypatch.setattr(settings, field, "")


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


@pytest.fixture
def make_client(fake_db):
    """Factory for multi-user scenarios (owner + invited manager/worker,
    or two separate orgs) sharing one in-memory Firestore. Usage:

        owner = make_client("uid-1", "owner@example.com")
        owner.post("/farms", json={"name": "Farm"})
        manager = make_client("uid-2", "mgr@example.com", org_id="uid-1")
        manager.get("/team")

    Each call switches which identity the shared TestClient authenticates
    as for subsequent requests (`org_id` sets the Firebase custom claim
    that `get_current_org_id`/`get_current_membership` read - passing it
    is how a test simulates "already accepted an invite" without going
    through the real Firebase Admin SDK).
    """
    app.dependency_overrides[get_firestore_client] = lambda: fake_db
    client = TestClient(app)

    def _as(uid: str, email: str, org_id: str | None = None, name: str | None = None) -> TestClient:
        token = {"uid": uid, "email": email}
        if name:
            token["name"] = name
        if org_id:
            token["org_id"] = org_id
        app.dependency_overrides[get_current_user] = lambda: token
        return client

    yield _as
    app.dependency_overrides.clear()


@pytest.fixture
def mock_firebase_claims(monkeypatch):
    """Team routes call the real firebase_admin.auth SDK to set/clear custom
    claims and revoke tokens - none of which can hit a real Firebase project
    in tests. This replaces those three calls with in-memory recorders so
    the app code under test runs unmodified, while asserting exactly what
    it tried to do to Firebase Auth.
    """
    calls = {"set_claims": [], "revoked": []}

    class _FakeFirebaseUser:
        custom_claims = None

    def fake_get_user(uid):
        return _FakeFirebaseUser()

    def fake_set_custom_user_claims(uid, claims):
        calls["set_claims"].append((uid, claims))

    def fake_revoke_refresh_tokens(uid):
        calls["revoked"].append(uid)

    monkeypatch.setattr("app.services.membership_service.firebase_auth.get_user", fake_get_user)
    monkeypatch.setattr(
        "app.services.membership_service.firebase_auth.set_custom_user_claims", fake_set_custom_user_claims
    )
    monkeypatch.setattr(
        "app.services.membership_service.firebase_auth.revoke_refresh_tokens", fake_revoke_refresh_tokens
    )
    return calls
