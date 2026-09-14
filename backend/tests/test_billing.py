import hashlib
import hmac
import json as jsonlib
from datetime import datetime, timezone

import app.services.paystack_service as paystack_service
from app.core.config import settings as app_settings
from app.core.refs import members_ref, subscription_ref
from app.services.billing_service import PLAN_CATALOG
from app.services.usage_service import current_period_key, usage_periods_ref

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


def test_pilot_subscription_returned_and_backfilled(authed_client):
    response = authed_client.get("/billing")
    assert response.status_code == 200
    body = response.json()
    assert body["subscription"]["plan"] == "pilot"
    assert body["subscription"]["status"] == "active"
    assert body["subscription"]["currency"] == "GHS"
    assert body["payments_active"] is False  # no PAYSTACK_SECRET_KEY set in tests
    plans_by_name = {p["plan"]: p for p in body["plans"]}
    assert plans_by_name["starter"]["price_ghs"] == 249
    assert plans_by_name["growth"]["price_ghs"] == 549
    assert plans_by_name["pro"]["price_ghs"] == 1199
    assert plans_by_name["enterprise"]["contact_sales"] is True
    assert plans_by_name["enterprise"]["price_ghs"] is None


def test_pilot_subscription_backfills_a_limit_key_added_after_the_org_was_created(authed_client, fake_db):
    # Simulates an org whose subscription doc predates ai_requests_monthly
    # existing at all - written directly, bypassing get_or_create_subscription,
    # the same way a real pre-existing Firestore doc would already lack it.
    from tests.conftest import FAKE_UID

    subscription_ref(fake_db, FAKE_UID).set(
        {
            "plan": "pilot",
            "status": "active",
            "currency": "GHS",
            "limits": {"houses": 5, "birds": 5000, "team_members": 5},  # no ai_requests_monthly
        }
    )

    usage = authed_client.get("/billing/usage").json()
    assert usage["ai_requests"]["limit"] == 200  # backfilled from current PILOT_LIMITS, not left missing

    # And it's persisted, not just patched in memory for this one response.
    stored = subscription_ref(fake_db, FAKE_UID).get().to_dict()
    assert stored["limits"]["ai_requests_monthly"] == 200
    assert stored["limits"]["houses"] == 5  # untouched - only the missing key was added


def test_real_house_and_bird_usage_calculated(authed_client):
    farm = authed_client.post("/farms", json={"name": "Farm"}).json()
    house_a = authed_client.post(f"/farms/{farm['id']}/houses", json={"name": "House A"}).json()
    house_b = authed_client.post(f"/farms/{farm['id']}/houses", json={"name": "House B"}).json()

    authed_client.post(
        f"/farms/{farm['id']}/houses/{house_a['id']}/flocks",
        json={"bird_type": "broiler", "breed": "Cobb 500", "start_date": "2026-01-01", "initial_bird_count": 1000},
    )
    authed_client.post(
        f"/farms/{farm['id']}/houses/{house_b['id']}/flocks",
        json={"bird_type": "broiler", "breed": "Ross 308", "start_date": "2026-01-01", "initial_bird_count": 500},
    )

    usage = authed_client.get("/billing/usage").json()
    assert usage["houses"]["used"] == 2
    assert usage["houses"]["limit"] == 5
    assert usage["birds"]["used"] == 1500  # no checks yet - falls back to initial_bird_count
    assert usage["birds"]["limit"] == 5000


def test_bird_usage_prefers_latest_check_over_initial_count(authed_client):
    farm = authed_client.post("/farms", json={"name": "Farm"}).json()
    house = authed_client.post(f"/farms/{farm['id']}/houses", json={"name": "House A"}).json()
    authed_client.post(
        f"/farms/{farm['id']}/houses/{house['id']}/flocks",
        json={"bird_type": "broiler", "breed": "Cobb 500", "start_date": "2026-01-01", "initial_bird_count": 1000},
    )
    authed_client.post(
        f"/farms/{farm['id']}/houses/{house['id']}/flock-checks",
        json={"period": "morning", "bird_count": 985, "mortality": 15},
    )

    usage = authed_client.get("/billing/usage").json()
    assert usage["birds"]["used"] == 985  # reflects mortality, not the stale initial count


def test_team_usage_calculated(make_client, fake_db):
    owner = make_client(OWNER_UID, OWNER_EMAIL)
    owner.get("/team")
    _seed_member(fake_db, OWNER_UID, "manager-1", "manager@example.com", "manager")
    _seed_member(fake_db, OWNER_UID, "worker-1", "worker@example.com", "worker")

    usage = owner.get("/billing/usage").json()
    assert usage["team_members"]["used"] == 3  # owner + manager + worker
    assert usage["team_members"]["limit"] == 5


def test_ai_requests_and_storage_are_really_tracked(authed_client, fake_db):
    usage = authed_client.get("/billing/usage").json()
    assert usage["ai_requests"] == {"used": 0, "limit": 200, "period": "monthly"}
    assert usage["storage"] == {"used_bytes": 0, "used_mb": 0.0}

    from tests.conftest import FAKE_UID

    usage_periods_ref(fake_db, FAKE_UID).document(current_period_key()).set({"ai_requests": 7})
    subscription_ref(fake_db, FAKE_UID).set({"storage_bytes": 2_097_152}, merge=True)

    usage = authed_client.get("/billing/usage").json()
    assert usage["ai_requests"]["used"] == 7
    assert usage["storage"] == {"used_bytes": 2_097_152, "used_mb": 2.0}


def test_house_limit_is_enforced_not_just_displayed(authed_client, fake_db):
    from tests.conftest import FAKE_UID

    subscription_ref(fake_db, FAKE_UID).set({"limits": {"houses": 2}}, merge=True)
    farm = authed_client.post("/farms", json={"name": "Farm"}).json()

    assert authed_client.post(f"/farms/{farm['id']}/houses", json={"name": "House A"}).status_code == 201
    assert authed_client.post(f"/farms/{farm['id']}/houses", json={"name": "House B"}).status_code == 201

    blocked = authed_client.post(f"/farms/{farm['id']}/houses", json={"name": "House C"})
    assert blocked.status_code == 402
    assert "house" in blocked.json()["detail"].lower()


def test_bird_limit_is_enforced_before_creating_an_over_limit_flock(authed_client, fake_db):
    from tests.conftest import FAKE_UID

    subscription_ref(fake_db, FAKE_UID).set({"limits": {"birds": 1000}}, merge=True)
    farm = authed_client.post("/farms", json={"name": "Farm"}).json()
    house = authed_client.post(f"/farms/{farm['id']}/houses", json={"name": "House A"}).json()

    ok = authed_client.post(
        f"/farms/{farm['id']}/houses/{house['id']}/flocks",
        json={"bird_type": "broiler", "breed": "Cobb 500", "start_date": "2026-01-01", "initial_bird_count": 900},
    )
    assert ok.status_code == 201

    blocked = authed_client.post(
        f"/farms/{farm['id']}/houses/{house['id']}/flocks",
        json={"bird_type": "broiler", "breed": "Cobb 500", "start_date": "2026-01-01", "initial_bird_count": 200},
    )
    assert blocked.status_code == 402
    assert "bird" in blocked.json()["detail"].lower()


def test_team_seat_limit_is_enforced_counting_pending_invites(authed_client, fake_db):
    from tests.conftest import FAKE_UID

    authed_client.get("/team")  # backfills the owner's own membership doc
    subscription_ref(fake_db, FAKE_UID).set({"limits": {"team_members": 2}}, merge=True)

    # Owner already fills 1 of 2 seats; one invite should succeed, a second should not.
    ok = authed_client.post("/team/invitations", json={"email": "manager@example.com", "role": "manager"})
    assert ok.status_code == 201

    blocked = authed_client.post("/team/invitations", json={"email": "worker@example.com", "role": "worker"})
    assert blocked.status_code == 402
    assert "seat" in blocked.json()["detail"].lower()


def test_worker_and_manager_cannot_access_billing(make_client, fake_db):
    owner = make_client(OWNER_UID, OWNER_EMAIL)
    owner.get("/team")
    _seed_member(fake_db, OWNER_UID, "manager-1", "manager@example.com", "manager")
    _seed_member(fake_db, OWNER_UID, "worker-1", "worker@example.com", "worker")

    manager = make_client("manager-1", "manager@example.com", org_id=OWNER_UID)
    worker = make_client("worker-1", "worker@example.com", org_id=OWNER_UID)

    for user in (manager, worker):
        assert user.get("/billing").status_code == 403
        assert user.get("/billing/usage").status_code == 403


def test_cross_org_billing_isolation(make_client):
    org_a = make_client("org-a-owner", "a@example.com")
    farm_a = org_a.post("/farms", json={"name": "Org A Farm"}).json()
    org_a.post(f"/farms/{farm_a['id']}/houses", json={"name": "House A1"})

    org_b = make_client("org-b-owner", "b@example.com")
    usage_b = org_b.get("/billing/usage").json()
    assert usage_b["houses"]["used"] == 0  # never sees org A's houses


def test_checkout_returns_paystacks_authorization_url(authed_client, monkeypatch):
    monkeypatch.setattr(app_settings, "paystack_plan_code_starter", "plm_starter_test")

    async def _fake_initialize(*, email, plan_code, callback_url, metadata):
        assert email == "farmer@example.com"  # authed_client's fake user
        assert plan_code == "plm_starter_test"
        assert metadata["plan"] == "starter"
        return {"authorization_url": "https://paystack.test/pay/abc", "access_code": "abc", "reference": "ref_123"}

    monkeypatch.setattr(paystack_service, "initialize_transaction", _fake_initialize)

    response = authed_client.post("/billing/checkout", json={"plan": "starter"})
    assert response.status_code == 200
    assert response.json() == {"authorization_url": "https://paystack.test/pay/abc", "reference": "ref_123"}


def test_checkout_rejects_enterprise_and_pilot_not_self_serve(authed_client):
    assert authed_client.post("/billing/checkout", json={"plan": "enterprise"}).status_code == 422
    assert authed_client.post("/billing/checkout", json={"plan": "pilot"}).status_code == 422


def test_checkout_fails_clearly_when_plan_not_yet_configured(authed_client):
    # No PAYSTACK_PLAN_CODE_GROWTH set - must not silently succeed or crash.
    response = authed_client.post("/billing/checkout", json={"plan": "growth"})
    assert response.status_code == 503


def test_verify_activates_the_paid_plan_with_real_limits(authed_client, monkeypatch):
    from tests.conftest import FAKE_UID

    async def _fake_verify(reference):
        assert reference == "ref_abc"
        return {
            "status": "success",
            "metadata": {"org_id": FAKE_UID, "plan": "starter"},
            "customer": {"customer_code": "CUS_123"},
            "authorization": {"authorization_code": "AUTH_123"},
            "plan": {"plan_code": "plm_starter_test", "next_payment_date": "2026-07-01T00:00:00.000Z"},
        }

    monkeypatch.setattr(paystack_service, "verify_transaction", _fake_verify)

    response = authed_client.post("/billing/verify", json={"reference": "ref_abc"})
    assert response.status_code == 200
    sub = response.json()["subscription"]
    assert sub["plan"] == "starter"
    assert sub["status"] == "active"
    assert sub["limits"] == PLAN_CATALOG["starter"]["limits"]
    assert sub["paystack_customer_code"] == "CUS_123"

    # Now actually enforced, not just displayed - the whole point.
    usage = authed_client.get("/billing/usage").json()
    assert usage["houses"]["limit"] == 10


def test_verify_handles_paystacks_real_response_shape_where_plan_is_a_bare_string(authed_client, monkeypatch):
    # Regression test: Paystack's actual /transaction/verify response
    # returns data.plan as a bare plan-code STRING (e.g. "PLN_abc123"), not
    # the nested {"plan_code": ...} object this code originally assumed -
    # that mismatch crashed activate_paid_plan with an AttributeError
    # ('str' object has no attribute 'get') the first time this was
    # actually exercised against the live Paystack API.
    from tests.conftest import FAKE_UID

    async def _fake_verify(reference):
        return {
            "status": "success",
            "metadata": {"org_id": FAKE_UID, "plan": "starter"},
            "customer": {"customer_code": "CUS_456"},
            "authorization": {"authorization_code": "AUTH_456"},
            "plan": "PLN_4lttx99q7g502n8",  # a bare string, not a dict
        }

    monkeypatch.setattr(paystack_service, "verify_transaction", _fake_verify)

    response = authed_client.post("/billing/verify", json={"reference": "ref_string_plan"})
    assert response.status_code == 200
    assert response.json()["subscription"]["plan"] == "starter"


def test_verify_rejects_a_failed_payment(authed_client, monkeypatch):
    async def _fake_verify(reference):
        return {"status": "failed"}

    monkeypatch.setattr(paystack_service, "verify_transaction", _fake_verify)
    assert authed_client.post("/billing/verify", json={"reference": "ref_bad"}).status_code == 402


def test_verify_rejects_a_payment_reference_from_another_org(authed_client, monkeypatch):
    async def _fake_verify(reference):
        return {"status": "success", "metadata": {"org_id": "some-other-org", "plan": "starter"}}

    monkeypatch.setattr(paystack_service, "verify_transaction", _fake_verify)
    assert authed_client.post("/billing/verify", json={"reference": "ref_x"}).status_code == 403


def test_cancel_disables_paystack_subscription_and_downgrades_to_pilot(authed_client, fake_db, monkeypatch):
    from tests.conftest import FAKE_UID

    subscription_ref(fake_db, FAKE_UID).set(
        {
            "plan": "starter",
            "status": "active",
            "limits": PLAN_CATALOG["starter"]["limits"],
            "paystack_subscription_code": "SUB_123",
            "paystack_email_token": "tok_123",
        },
        merge=True,
    )

    calls = {}

    async def _fake_disable(*, subscription_code, email_token):
        calls["subscription_code"] = subscription_code
        calls["email_token"] = email_token

    monkeypatch.setattr(paystack_service, "disable_subscription", _fake_disable)

    response = authed_client.post("/billing/cancel")
    assert response.status_code == 200
    assert response.json()["subscription"]["plan"] == "pilot"
    assert response.json()["subscription"]["limits"] == {
        "houses": 5,
        "birds": 5000,
        "team_members": 5,
        "ai_requests_monthly": 200,
    }
    assert calls == {"subscription_code": "SUB_123", "email_token": "tok_123"}


def test_webhook_rejects_a_bad_signature(make_client):
    client = make_client("whoever", "whoever@example.com")  # only to get fake_db wired in
    response = client.post(
        "/billing/webhook", content=b'{"event": "charge.success"}', headers={"x-paystack-signature": "bogus"}
    )
    assert response.status_code == 401


def test_webhook_activates_plan_on_charge_success(make_client, fake_db, monkeypatch):
    monkeypatch.setattr(app_settings, "paystack_secret_key", "sk_test_123")
    client = make_client("whoever", "whoever@example.com")  # only to get fake_db wired in

    body = jsonlib.dumps(
        {
            "event": "charge.success",
            "data": {
                "status": "success",
                "metadata": {"org_id": "org-webhook-1", "plan": "growth"},
                "customer": {"customer_code": "CUS_999"},
                "plan": {"plan_code": ""},
            },
        }
    ).encode()
    signature = hmac.new(b"sk_test_123", body, hashlib.sha512).hexdigest()

    response = client.post(
        "/billing/webhook",
        content=body,
        headers={"x-paystack-signature": signature, "content-type": "application/json"},
    )
    assert response.status_code == 200

    sub = subscription_ref(fake_db, "org-webhook-1").get().to_dict()
    assert sub["plan"] == "growth"
    assert sub["status"] == "active"


def test_webhook_downgrades_on_subscription_disable(make_client, fake_db, monkeypatch):
    monkeypatch.setattr(app_settings, "paystack_secret_key", "sk_test_123")
    client = make_client("whoever", "whoever@example.com")

    subscription_ref(fake_db, "org-webhook-2").set(
        {"plan": "pro", "status": "active", "paystack_customer_code": "CUS_777"}, merge=True
    )

    body = jsonlib.dumps(
        {"event": "subscription.disable", "data": {"customer": {"customer_code": "CUS_777"}}}
    ).encode()
    signature = hmac.new(b"sk_test_123", body, hashlib.sha512).hexdigest()

    response = client.post(
        "/billing/webhook",
        content=body,
        headers={"x-paystack-signature": signature, "content-type": "application/json"},
    )
    assert response.status_code == 200

    sub = subscription_ref(fake_db, "org-webhook-2").get().to_dict()
    assert sub["plan"] == "pilot"
    assert sub["status"] == "cancelled"
