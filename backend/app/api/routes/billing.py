"""Billing/subscription. PILOT is free with no payment processing involved
at all. Starter/Growth/Pro are real, paid, Paystack-backed plans - checkout,
verification, cancellation and webhook-driven lifecycle updates all live
here. Enterprise stays contact-sales only; there is no self-serve checkout
for it (see CheckoutRequest's validator and BillingPage.jsx).

Owner-only throughout EXCEPT the webhook, which Paystack calls directly with
no Firebase token at all - it's authenticated by HMAC signature instead (see
paystack_service.verify_webhook_signature), never by
app/core/permissions.py::require_owner.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from google.cloud.firestore import Client

from app.core.config import settings
from app.core.firestore import get_firestore_client
from app.core.permissions import require_owner
from app.models.schemas import CheckoutRequest, VerifyPaymentRequest
from app.services import paystack_service
from app.services.billing_service import (
    PILOT_LIMITS,
    PLAN_CATALOG,
    activate_paid_plan,
    downgrade_to_pilot,
    extract_plan_code,
    find_org_id_by_paystack_customer_code,
    get_or_create_subscription,
    mark_payment_failed,
    plan_code_for,
    plan_for_paystack_plan_code,
    record_subscription_created,
)
from app.services.usage_service import (
    count_birds,
    count_houses,
    count_team_seats,
    get_ai_requests_this_month,
    get_storage_bytes,
)

_logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["billing"])

PLANS = [
    {"plan": plan, "price_ghs": info["price_ghs"], "currency": "GHS", "limits": info["limits"]}
    for plan, info in PLAN_CATALOG.items()
] + [{"plan": "enterprise", "price_ghs": None, "currency": "GHS", "limits": None, "contact_sales": True}]


@router.get("")
def get_billing(
    membership: dict = Depends(require_owner),
    db: Client = Depends(get_firestore_client),
):
    subscription = get_or_create_subscription(db, membership["org_id"])
    return {
        "subscription": subscription,
        "payments_active": bool(settings.paystack_secret_key),
        "note": (
            "FlockGuard is in pilot - no payment processing is active yet. This plan is free."
            if subscription.get("plan") == "pilot"
            else None
        ),
        "plans": PLANS,
    }


@router.get("/usage")
def get_usage(
    membership: dict = Depends(require_owner),
    db: Client = Depends(get_firestore_client),
):
    """Every number here is real: houses/birds/team seats are counted live
    from Firestore on every call (see app/services/usage_service.py), and AI
    requests/storage are running counters incremented at the point of use
    (app/agent/flockguard_agent.py, app/api/routes/ask.py and media.py) -
    nothing here is hard-coded or estimated."""
    org_id = membership["org_id"]
    subscription = get_or_create_subscription(db, org_id)
    limits = subscription.get("limits", PILOT_LIMITS)

    storage_bytes = get_storage_bytes(db, org_id)

    return {
        "houses": {"used": count_houses(db, org_id), "limit": limits.get("houses")},
        "birds": {"used": count_birds(db, org_id), "limit": limits.get("birds")},
        "team_members": {"used": count_team_seats(db, org_id), "limit": limits.get("team_members")},
        "ai_requests": {
            "used": get_ai_requests_this_month(db, org_id),
            "limit": limits.get("ai_requests_monthly"),
            "period": "monthly",
        },
        "storage": {
            "used_bytes": storage_bytes,
            "used_mb": round(storage_bytes / (1024 * 1024), 1),
        },
    }


@router.post("/checkout")
async def checkout(
    payload: CheckoutRequest,
    membership: dict = Depends(require_owner),
    db: Client = Depends(get_firestore_client),
):
    """Starts a Paystack checkout for one of the paid plans. Returns
    `authorization_url` - the frontend redirects the browser there; Paystack
    redirects back to `{app_public_url}/billing?reference=...` on
    completion, where the frontend calls POST /billing/verify."""
    plan = payload.plan.value
    plan_code = plan_code_for(plan)
    if not plan_code:
        raise HTTPException(status_code=503, detail=f"The {plan} plan isn't available for checkout yet.")

    org_id = membership["org_id"]
    data = await paystack_service.initialize_transaction(
        email=membership.get("email") or "",
        plan_code=plan_code,
        callback_url=f"{settings.app_public_url}/billing",
        metadata={"org_id": org_id, "plan": plan},
    )
    return {"authorization_url": data["authorization_url"], "reference": data["reference"]}


@router.post("/verify")
async def verify_payment(
    payload: VerifyPaymentRequest,
    membership: dict = Depends(require_owner),
    db: Client = Depends(get_firestore_client),
):
    """Confirms a just-completed checkout and activates the plan - the
    frontend calls this right after Paystack redirects back. Belt-and-
    braces alongside the webhook below: this gives the user immediate
    feedback without waiting on webhook delivery, while the webhook remains
    the authoritative path for renewals and anything that happens after the
    browser tab is long closed."""
    org_id = membership["org_id"]
    data = await paystack_service.verify_transaction(payload.reference)

    if data.get("status") != "success":
        raise HTTPException(status_code=402, detail="This payment was not successful.")

    metadata = data.get("metadata") or {}
    if metadata.get("org_id") and metadata["org_id"] != org_id:
        raise HTTPException(status_code=403, detail="This payment reference belongs to a different organization.")

    plan = metadata.get("plan") or plan_for_paystack_plan_code(extract_plan_code(data))
    if plan not in PLAN_CATALOG:
        raise HTTPException(status_code=502, detail="Could not determine which plan this payment was for.")

    subscription = activate_paid_plan(db, org_id, plan=plan, paystack_data=data)
    return {"subscription": subscription}


@router.post("/cancel")
async def cancel_subscription(
    membership: dict = Depends(require_owner),
    db: Client = Depends(get_firestore_client),
):
    """Cancels future billing and drops back to the free PILOT plan.
    Paystack keeps the current paid period running (no partial refund) -
    only the next charge is what gets cancelled."""
    org_id = membership["org_id"]
    subscription = get_or_create_subscription(db, org_id)

    subscription_code = subscription.get("paystack_subscription_code")
    email_token = subscription.get("paystack_email_token")
    if subscription_code and email_token:
        await paystack_service.disable_subscription(subscription_code=subscription_code, email_token=email_token)

    downgrade_to_pilot(db, org_id)
    return {"subscription": get_or_create_subscription(db, org_id)}


@router.post("/webhook", include_in_schema=False)
async def paystack_webhook(request: Request, db: Client = Depends(get_firestore_client)):
    """No Firebase auth at all - Paystack calls this directly. Authenticated
    purely by HMAC signature (see paystack_service.verify_webhook_signature);
    the raw body must be read BEFORE any JSON parsing, since the signature
    covers the exact bytes Paystack sent."""
    body = await request.body()
    signature = request.headers.get("x-paystack-signature")
    if not paystack_service.verify_webhook_signature(body, signature):
        raise HTTPException(status_code=401, detail="Invalid Paystack signature")

    payload = await request.json()
    event = payload.get("event")
    data = payload.get("data") or {}
    _logger.info("Paystack webhook received: %s", event)

    metadata = data.get("metadata") or {}
    customer_code = (data.get("customer") or {}).get("customer_code")
    org_id = metadata.get("org_id") or (
        find_org_id_by_paystack_customer_code(db, customer_code) if customer_code else None
    )
    if not org_id:
        # Nothing to attach this event to - log and 200 anyway so Paystack
        # doesn't endlessly retry an event we will never be able to place.
        _logger.warning("Paystack webhook %s: could not resolve an org_id, dropping", event)
        return {"received": True}

    if event == "charge.success":
        plan = metadata.get("plan") or plan_for_paystack_plan_code(extract_plan_code(data))
        if plan in PLAN_CATALOG:
            activate_paid_plan(db, org_id, plan=plan, paystack_data=data)
    elif event == "subscription.create":
        subscription_code = data.get("subscription_code")
        email_token = data.get("email_token")
        if subscription_code and email_token:
            record_subscription_created(db, org_id, subscription_code=subscription_code, email_token=email_token)
    elif event in ("subscription.disable", "subscription.not_renew"):
        downgrade_to_pilot(db, org_id, status="cancelled")
    elif event == "invoice.payment_failed":
        mark_payment_failed(db, org_id)

    return {"received": True}
