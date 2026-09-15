"""Web Push via Firebase Cloud Messaging.

Reuses the same Admin SDK credentials already initialized in
app/core/firebase.py for Auth/Firestore - FCM needs no separate API key or
config on the backend. The client side (permission prompt, token retrieval,
and the firebase-messaging-sw.js service worker that receives pushes while
the tab is closed) lives in frontend/src/lib/push.js.

Gating (whether an alert should push at all) is decided by
app/services/notification_service.py::push_enabled, the same "channel +
severity toggle" rule email uses - this module only knows how to register,
send to, and prune tokens.
"""

import logging
from datetime import datetime, timezone

from firebase_admin import messaging
from google.cloud.firestore import Client

from app.core.refs import push_tokens_ref

_logger = logging.getLogger(__name__)


def register_token(db: Client, *, org_id: str, uid: str, token: str) -> None:
    """Idempotent upsert - re-registering the same device (e.g. on every
    login) just refreshes updated_at rather than creating a duplicate,
    since the token itself is the document id."""
    push_tokens_ref(db, org_id, uid).document(token).set(
        {"token": token, "updated_at": datetime.now(timezone.utc).isoformat()}
    )


def unregister_token(db: Client, *, org_id: str, uid: str, token: str) -> None:
    push_tokens_ref(db, org_id, uid).document(token).delete()


def _tokens_by_uid(db: Client, org_id: str, uids: list[str]) -> dict[str, list[str]]:
    return {uid: [doc.id for doc in push_tokens_ref(db, org_id, uid).stream()] for uid in uids}


def send_push_to_uids(db: Client, *, org_id: str, uids: list[str], title: str, body: str, url: str) -> bool:
    """Best-effort, mirrors email_service._send: never raises, returns
    whether at least one device was actually reached. A token FCM reports as
    UnregisteredError (uninstalled, permission revoked, browser data
    cleared) is pruned immediately so it's never retried on a later alert."""
    sent_any = False
    for uid, tokens in _tokens_by_uid(db, org_id, uids).items():
        for token in tokens:
            # Sent as a pure data message (no top-level `notification` field)
            # rather than a "notification message" - the notification/data
            # split determines who's responsible for displaying it, and
            # notification messages are handled inconsistently across
            # browsers when the tab is in the foreground (sometimes routed
            # to the service worker anyway, so the in-app toast in
            # AppLayout.jsx never fires). Data-only messages are always
            # delivered to app code (foreground: onMessage in
            # frontend/src/lib/push.js; background: onBackgroundMessage in
            # public/firebase-messaging-sw.js), giving one predictable path.
            # (data field values must all be strings, hence str(url).)
            message = messaging.Message(data={"title": title, "body": body, "url": str(url)}, token=token)
            try:
                messaging.send(message)
                sent_any = True
            except messaging.UnregisteredError:
                push_tokens_ref(db, org_id, uid).document(token).delete()
            except Exception:  # noqa: BLE001 - one bad token/outage must never block the rest
                _logger.exception("Failed to send push notification to uid=%s", uid)
    return sent_any
