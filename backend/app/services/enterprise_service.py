"""Enterprise leads: who asked for Enterprise (the Billing page's "Request
Enterprise" form), what happened next, and who we should offer it to even
though they haven't asked.

    enterprise_requests/{id} = {
        org_id, uid, email, display_name, farm_name,
        current_plan, usage: {houses, birds, team_members, ai_requests_month},
        requested: {houses, birds}, phone, contact_method, message,
        status: new | contacted | won | lost,
        notes: [{text, by, at}], created_at, updated_at
    }

Top-level (not under the org) so the admin console lists every lead in one
query, and backend-only in firestore.rules like admin_audit_log.
"""

from datetime import datetime, timezone

from fastapi import HTTPException
from google.cloud.firestore import Client, Query

from app.models.schemas import SubscriptionPlan

OPEN_STATUSES = {"new", "contacted"}

# Upgrade-candidate heuristics (build_upgrade_candidates).
NEAR_LIMIT_RATIO = 0.8
BIG_OPERATION_HOUSES = 15
BIG_TEAM_MEMBERS = 5
CANDIDATE_PLANS = {SubscriptionPlan.GROWTH.value, SubscriptionPlan.PRO.value}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def requests_ref(db: Client):
    return db.collection("enterprise_requests")


def open_request_for_org(db: Client, org_id: str) -> dict | None:
    for snap in requests_ref(db).where("org_id", "==", org_id).stream():
        data = snap.to_dict()
        if data.get("status") in OPEN_STATUSES:
            return {"id": snap.id, **data}
    return None


def create_request(db: Client, *, membership: dict, user: dict, payload, current_plan: str, usage: dict,
                   farm_name: str | None) -> tuple[dict, bool]:
    """Returns (request, created). An org with an open request gets that one
    back instead of a duplicate."""
    existing = open_request_for_org(db, membership["org_id"])
    if existing:
        return existing, False

    now = _now_iso()
    doc = {
        "org_id": membership["org_id"],
        "uid": user["uid"],
        "email": user.get("email") or membership.get("email"),
        "display_name": user.get("name") or membership.get("display_name"),
        "farm_name": farm_name,
        "current_plan": current_plan,
        "usage": usage,
        "requested": {"houses": payload.houses, "birds": payload.birds},
        "phone": (payload.phone or "").strip() or None,
        "contact_method": payload.contact_method.value,
        "message": (payload.message or "").strip() or None,
        "status": "new",
        "notes": [],
        "created_at": now,
        "updated_at": now,
    }
    ref = requests_ref(db).document()
    ref.set(doc)
    return {"id": ref.id, **doc}, True


def list_requests(db: Client) -> list[dict]:
    docs = requests_ref(db).order_by("created_at", direction=Query.DESCENDING).limit(500).stream()
    return [{"id": d.id, **d.to_dict()} for d in docs]


def get_request_or_404(db: Client, request_id: str) -> dict:
    snap = requests_ref(db).document(request_id).get()
    if not snap.exists:
        raise HTTPException(status_code=404, detail="Enterprise request not found")
    return {"id": snap.id, **snap.to_dict()}


def update_request(db: Client, request_id: str, *, status: str | None, note: str | None, admin: dict) -> tuple[dict, dict]:
    """Returns (before, after)."""
    before = get_request_or_404(db, request_id)
    update = {"updated_at": _now_iso()}
    if status:
        update["status"] = status
    if note:
        update["notes"] = before.get("notes", []) + [
            {"text": note, "by": admin.get("email") or admin["uid"], "at": _now_iso()}
        ]
    requests_ref(db).document(request_id).set(update, merge=True)
    return before, {**before, **update}


def build_upgrade_candidates(orgs: list[dict], open_request_org_ids: set[str]) -> list[dict]:
    """Orgs worth offering Enterprise to, with the reasons why. `orgs` are
    admin_service.build_platform_snapshot rows."""
    candidates = []
    for o in orgs:
        if o["plan"] == SubscriptionPlan.ENTERPRISE.value or o["platform_status"] == "suspended":
            continue
        reasons = []
        on_top_plan = o["plan"] in CANDIDATE_PLANS
        for key, label in (("house_usage_ratio", "houses"), ("ai_usage_ratio", "AI requests")):
            ratio = o.get(key)
            if on_top_plan and ratio is not None and ratio >= NEAR_LIMIT_RATIO:
                reasons.append(f"{round(ratio * 100)}% of {label} limit")
        if o["houses"] >= BIG_OPERATION_HOUSES:
            reasons.append(f"{o['houses']} houses")
        if o["farm_count"] >= 3:
            reasons.append(f"{o['farm_count']} farms")
        if o["members_active"] >= BIG_TEAM_MEMBERS:
            reasons.append(f"{o['members_active']} team members")
        if o["org_id"] in open_request_org_ids:
            reasons.insert(0, "asked for Enterprise")
        if not reasons:
            continue
        candidates.append(
            {
                "org_id": o["org_id"],
                "farm_name": o["farms"][0]["name"] if o["farms"] else None,
                "owner_email": o["owner_email"],
                "plan": o["plan"],
                "houses": o["houses"],
                "members_active": o["members_active"],
                "checks_30d": o["checks_30d"],
                "house_usage_ratio": o["house_usage_ratio"],
                "ai_usage_ratio": o["ai_usage_ratio"],
                "reasons": reasons,
                "has_open_request": o["org_id"] in open_request_org_ids,
            }
        )
    candidates.sort(key=lambda c: (c["has_open_request"], len(c["reasons"]), c["checks_30d"]), reverse=True)
    return candidates[:50]
