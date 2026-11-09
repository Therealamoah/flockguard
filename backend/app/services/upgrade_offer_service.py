"""Admin-suggested upgrades that the farmer accepts - and pays for - themselves.

An admin picks a paid plan for an org (Admin → org page → Offer upgrade). The
org's owner gets an email and an in-app banner pointing at Billing, where the
normal Paystack checkout takes over. Nothing about the org's plan changes
until they pay; compare the admin "Change plan" override, which switches the
plan immediately with no payment at all.

Stored as a sibling of the subscription's `current` doc:

    organizations/{org}/subscription/upgrade_offer = {
        plan, message, offered_by, offered_at, status: open | dismissed | withdrawn,
        email_sent
    }

"Accepted" is never stored - an offer counts as accepted as soon as the org's
real plan reaches the offered plan, however they got there.
"""

from datetime import datetime, timezone

from fastapi import HTTPException
from google.cloud.firestore import Client

from app.core.refs import organization_ref
from app.services.billing_service import PLAN_CATALOG, get_or_create_subscription

PLAN_RANK = {"pilot": 0, "starter": 1, "growth": 2, "pro": 3, "enterprise": 4}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def offer_ref(db: Client, org_id: str):
    return organization_ref(db, org_id).collection("subscription").document("upgrade_offer")


def get_offer(db: Client, org_id: str) -> dict | None:
    """The stored offer with its effective status (adds "accepted")."""
    snap = offer_ref(db, org_id).get()
    if not snap.exists:
        return None
    offer = snap.to_dict()
    current_plan = get_or_create_subscription(db, org_id).get("plan", "pilot")
    if PLAN_RANK.get(current_plan, 0) >= PLAN_RANK.get(offer["plan"], 0):
        offer["status"] = "accepted"
    offer["current_plan"] = current_plan
    offer["price_ghs"] = PLAN_CATALOG.get(offer["plan"], {}).get("price_ghs")
    offer["limits"] = PLAN_CATALOG.get(offer["plan"], {}).get("limits")
    return offer


def get_open_offer(db: Client, org_id: str) -> dict | None:
    offer = get_offer(db, org_id)
    return offer if offer and offer["status"] == "open" else None


def create_offer(db: Client, org_id: str, *, plan: str, message: str | None, admin: dict) -> dict:
    current_plan = get_or_create_subscription(db, org_id).get("plan", "pilot")
    if PLAN_RANK.get(plan, 0) <= PLAN_RANK.get(current_plan, 0):
        raise HTTPException(status_code=409, detail=f"They're already on {current_plan} - offer a higher plan.")
    offer_ref(db, org_id).set(
        {
            "plan": plan,
            "message": (message or "").strip() or None,
            "offered_by": admin.get("email") or admin["uid"],
            "offered_at": _now_iso(),
            "status": "open",
            "email_sent": False,
        }
    )
    return get_offer(db, org_id)


def set_status(db: Client, org_id: str, status: str) -> dict | None:
    if not offer_ref(db, org_id).get().exists:
        return None
    offer_ref(db, org_id).set({"status": status, "status_changed_at": _now_iso()}, merge=True)
    return get_offer(db, org_id)


def mark_email_sent(db: Client, org_id: str) -> None:
    offer_ref(db, org_id).set({"email_sent": True}, merge=True)
