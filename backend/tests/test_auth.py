from firebase_admin import auth as firebase_auth

import app.api.routes.auth as auth_module


def test_forgot_password_sends_branded_email_for_existing_user(client, monkeypatch):
    monkeypatch.setattr(
        auth_module.firebase_auth,
        "generate_password_reset_link",
        lambda email: f"https://flockguard-test.firebaseapp.com/__/auth/action?mode=resetPassword&email={email}",
    )

    calls = {}

    async def _fake_send(*, to_email, reset_link):
        calls["to_email"] = to_email
        calls["reset_link"] = reset_link
        return True

    monkeypatch.setattr(auth_module, "send_password_reset_email", _fake_send)

    response = client.post("/auth/forgot-password", json={"email": "farmer@example.com"})
    assert response.status_code == 200
    assert response.json() == auth_module.GENERIC_RESPONSE
    assert calls["to_email"] == "farmer@example.com"
    assert "resetPassword" in calls["reset_link"]


def test_forgot_password_never_reveals_whether_the_email_has_an_account(client, monkeypatch):
    """Same generic response for an unknown email as a real one - anything
    else would let someone enumerate registered users one guess at a time."""

    def _raise_not_found(email):
        raise firebase_auth.UserNotFoundError("no such user")

    monkeypatch.setattr(auth_module.firebase_auth, "generate_password_reset_link", _raise_not_found)

    sent = {"called": False}

    async def _fake_send(*, to_email, reset_link):
        sent["called"] = True
        return True

    monkeypatch.setattr(auth_module, "send_password_reset_email", _fake_send)

    response = client.post("/auth/forgot-password", json={"email": "nobody@example.com"})
    assert response.status_code == 200
    assert response.json() == auth_module.GENERIC_RESPONSE
    assert sent["called"] is False  # never sends an email for an account that doesn't exist


def test_forgot_password_rejects_malformed_email(client):
    response = client.post("/auth/forgot-password", json={"email": "not-an-email"})
    assert response.status_code == 422
