from unittest.mock import patch

from app.core.refs import push_tokens_ref
from app.services.push_service import register_token, send_push_to_uids, unregister_token
from tests.conftest import FAKE_UID


def test_register_token_is_idempotent(fake_db):
    register_token(fake_db, org_id=FAKE_UID, uid=FAKE_UID, token="tok-1")
    register_token(fake_db, org_id=FAKE_UID, uid=FAKE_UID, token="tok-1")

    tokens = [doc.id for doc in push_tokens_ref(fake_db, FAKE_UID, FAKE_UID).stream()]
    assert tokens == ["tok-1"]


def test_unregister_token_removes_it(fake_db):
    register_token(fake_db, org_id=FAKE_UID, uid=FAKE_UID, token="tok-1")
    unregister_token(fake_db, org_id=FAKE_UID, uid=FAKE_UID, token="tok-1")

    tokens = [doc.id for doc in push_tokens_ref(fake_db, FAKE_UID, FAKE_UID).stream()]
    assert tokens == []


def test_send_push_to_uids_with_no_registered_tokens_does_nothing(fake_db):
    sent = send_push_to_uids(fake_db, org_id=FAKE_UID, uids=[FAKE_UID], title="t", body="b", url="/alerts")
    assert sent is False


def test_send_push_to_uids_sends_one_message_per_token(fake_db):
    register_token(fake_db, org_id=FAKE_UID, uid=FAKE_UID, token="tok-1")
    register_token(fake_db, org_id=FAKE_UID, uid=FAKE_UID, token="tok-2")

    with patch("app.services.push_service.messaging.send") as fake_send:
        sent = send_push_to_uids(fake_db, org_id=FAKE_UID, uids=[FAKE_UID], title="t", body="b", url="/alerts")

    assert sent is True
    assert fake_send.call_count == 2


def test_send_push_to_uids_prunes_unregistered_tokens(fake_db):
    from firebase_admin import messaging

    register_token(fake_db, org_id=FAKE_UID, uid=FAKE_UID, token="dead-token")

    with patch("app.services.push_service.messaging.send", side_effect=messaging.UnregisteredError("gone")):
        sent = send_push_to_uids(fake_db, org_id=FAKE_UID, uids=[FAKE_UID], title="t", body="b", url="/alerts")

    assert sent is False
    tokens = [doc.id for doc in push_tokens_ref(fake_db, FAKE_UID, FAKE_UID).stream()]
    assert tokens == []


def test_register_and_unregister_push_token_routes(authed_client):
    response = authed_client.post("/settings/push-token", json={"token": "tok-1"})
    assert response.status_code == 200
    assert response.json() == {"registered": True}

    response = authed_client.post("/settings/push-token/unregister", json={"token": "tok-1"})
    assert response.status_code == 200
    assert response.json() == {"registered": False}
