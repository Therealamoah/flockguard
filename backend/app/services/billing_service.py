"""Real subscription state - one Firestore document per org, self-healing
via get_or_create the same way membership_service.get_or_create_membership
backfills a membership for orgs that predate a feature, so no migration
script is needed for orgs that predate billing either.

PLAN_CATALOG is the single source of truth for pricing and limits on the
three self-serve paid tiers (Starter/Growth/Pro) - app/api/routes/billing.py
reads it for /billing/plans, checkout, and webhook handling all reuse it, so
a price or limit only ever needs changing in one place. Enterprise has no
entry here on purpose - it's contact-sales only, never self-serve checkout
(see BillingPage.jsx).
"""

from datetime import datetime, timezone

from google.cloud.firestore import Client

from app.core.config import settings
from app.core.refs import subscription_ref
from app.models.schemas import SubscriptionPlan

PILOT_LIMITS = {
    "houses": 5,
    "birds": 5000,
    "team_members": 5,
    "ai_requests_monthly": 200,
}

# price_ghs is the major unit (what a human reads, and what /billing/plans
# returns to the frontend) - Paystack itself is only ever given the
# pre-created Plan code below (see config.py's PAYSTACK_PLAN_CODE_* comment
# for why a raw amount isn't enough for recurring billing), never this
# number directly, so there's no pesewas conversion to keep in sync here.
PLAN_CATALOG = {
    SubscriptionPlan.STARTER.value: {
        "price_ghs": 249,
        "limits": {"houses": 10, "birds": 15_000, "team_members": 8, "ai_requests_monthly": 1_000},
    },
    SubscriptionPlan.GROWTH.value: {
        "price_ghs": 549,
        "limits": {"houses": 25, "birds": 50_000, "team_members": 15, "ai_requests_monthly": 3_000},
    },
    SubscriptionPlan.PRO.value: {
        "price_ghs": 1_199,
        "limits": {"houses": 60, "birds": 150_000, "team_members": 30, "ai_requests_monthly": 7_500},
    },
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def plan_code_for(plan: str) -> str | None:
    """The Paystack Plan code backing one of our paid tiers."""
    return {
        SubscriptionPlan.STARTER.value: settings.paystack_plan_code_starter,
        SubscriptionPlan.GROWTH.value: settings.paystack_plan_code_growth,
        SubscriptionPlan.PRO.value: settings.paystack_plan_code_pro,
    }.get(plan) or None


def plan_for_paystack_plan_code(plan_code: str | None) -> str | None:
    """Reverse lookup - webhooks identify the plan by Paystack's own plan
    code (data.plan.plan_code), not by anything this app chose itself."""
    if not plan_code:
        return None
    for plan in (SubscriptionPlan.STARTER.value, SubscriptionPlan.GROWTH.value, SubscriptionPlan.PRO.value):
        if plan_code_for(plan) == plan_code:
            return plan
    return None


def get_or_create_subscription(db: Client, org_id: str) -> dict:
    doc_ref = subscription_ref(db, org_id)
    snap = doc_ref.get()
    if snap.exists:
        subscription = snap.to_dict()
        if subscription.get("plan") == SubscriptionPlan.PILOT.value:
            # Backfill any limit keys PILOT_LIMITS has gained since this
            # org's doc was first written - get_or_create only writes once,
            # so an org that predates a newer limit (e.g.
            # ai_requests_monthly) would otherwise be stuck without it
            # forever, showing as an unenforced "no limit" instead of the
            # real PILOT cap. Only ever fills in a MISSING key, never
            # overwrites one that's already there, and only for PILOT - a
            # paid plan's limits are a commitment made at checkout, not
            # something to silently change later just because
            # PLAN_CATALOG's numbers moved since.
            limits = subscription.get("limits") or {}
            missing = {k: v for k, v in PILOT_LIMITS.items() if k not in limits}
            if missing:
                limits = {**limits, **missing}
                subscription["limits"] = limits
                doc_ref.set({"limits": limits}, merge=True)
        return subscription

    subscription = {
        "plan": SubscriptionPlan.PILOT.value,
        "status": "active",
        "billing_interval": None,
        "currency": "GHS",
        "price_ghs": 0,
        "started_at": _now_iso(),
        "trial_ends_at": None,
        "limits": PILOT_LIMITS,
    }
    doc_ref.set(subscription)
    return subscription


# Alias for call sites (houses.py, flocks.py, team.py, ask.py) that only
# want to read the current plan/limits to enforce them - not display or
# otherwise manage billing state themselves.
get_subscription = get_or_create_subscription


def extract_plan_code(paystack_data: dict) -> str | None:
    """Paystack is inconsistent about the shape of `data.plan` across
    endpoints/events: on /transaction/verify it's often just the plan code
    as a bare string, while other payloads (e.g. some webhook events) nest
    it as {"plan_code": ...}. Handles both rather than assuming one."""
    plan_field = paystack_data.get("plan")
    if isinstance(plan_field, dict):
        return plan_field.get("plan_code")
    if isinstance(plan_field, str) and plan_field:
        return plan_field
    return None


def activate_paid_plan(db: Client, org_id: str, *, plan: str, paystack_data: dict) -> dict:
    """Called from both /billing/verify and the charge.success webhook -
    "a payment for this plan succeeded" is the same event either way, so
    both funnel through this one update so the two paths can't drift apart.
    """
    customer = paystack_data.get("customer") or {}
    plan_field = paystack_data.get("plan")
    plan_info = plan_field if isinstance(plan_field, dict) else {}
    authorization = paystack_data.get("authorization") or {}

    update = {
        "plan": plan,
        "status": "active",
        "billing_interval": "monthly",
        "currency": "GHS",
        "limits": PLAN_CATALOG[plan]["limits"],
        "price_ghs": PLAN_CATALOG[plan]["price_ghs"],
        "updated_at": _now_iso(),
    }
    if customer.get("customer_code"):
        update["paystack_customer_code"] = customer["customer_code"]
    if authorization.get("authorization_code"):
        update["paystack_authorization_code"] = authorization["authorization_code"]
    if plan_info.get("next_payment_date"):
        update["current_period_end"] = plan_info["next_payment_date"]

    doc_ref = subscription_ref(db, org_id)
    doc_ref.set(update, merge=True)
    return doc_ref.get().to_dict()


def record_subscription_created(db: Client, org_id: str, *, subscription_code: str, email_token: str) -> None:
    """Paystack only ever hands out the email_token once, on the
    subscription.create webhook event - it's required later to cancel (see
    paystack_service.disable_subscription), so it must be persisted now or
    this org can never self-serve cancel again."""
    subscription_ref(db, org_id).set(
        {"paystack_subscription_code": subscription_code, "paystack_email_token": email_token}, merge=True
    )


def downgrade_to_pilot(db: Client, org_id: str, *, status: str = "cancelled") -> None:
    subscription_ref(db, org_id).set(
        {
            "plan": SubscriptionPlan.PILOT.value,
            "status": status,
            "limits": PILOT_LIMITS,
            "price_ghs": 0,
            "updated_at": _now_iso(),
        },
        merge=True,
    )


def mark_payment_failed(db: Client, org_id: str) -> None:
    subscription_ref(db, org_id).set({"status": "past_due", "updated_at": _now_iso()}, merge=True)


def find_org_id_by_paystack_customer_code(db: Client, customer_code: str) -> str | None:
    """Webhook events identify the payer by Paystack's own customer_code,
    never by an org_id we control - this is how a webhook (subscription.*,
    a renewal charge.success with no metadata) maps back to one of our
    orgs. Deliberately no `.limit(1)` here - collection-group + limit isn't
    exercised by anything else in this codebase and isn't worth the risk of
    an unnoticed pagination edge case for a lookup that only runs on a
    handful of webhook deliveries."""
    docs = db.collection_group("subscription").where("paystack_customer_code", "==", customer_code).stream()
    doc = next(docs, None)
    return doc.reference.parent.parent.id if doc else None
