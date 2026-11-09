"""Cross-organization reads and operator actions for the platform admin
console (app/api/routes/admin.py).

Organizations are discovered from their subcollections (members, farms,
subscription) rather than by listing `organizations` documents - nothing in
this codebase ever writes the org document itself, so in real Firestore it
only exists as an empty parent path that `.stream()` would never return.

Every collection group here is streamed WITHOUT filters and filtered in
Python. That keeps the console working with zero extra collection-group
indexes, and is cheap at pilot scale (tens of orgs). Once the platform has
thousands of flock checks a day, move the overview numbers to a scheduled
daily snapshot document instead of re-scanning on every page load.
"""

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from firebase_admin import auth as firebase_auth
from google.cloud.firestore import Client, Query

from app.core.refs import members_ref, organization_ref
from app.models.schemas import SubscriptionPlan
from app.services.activity_service import days_active, load_activity
from app.services.billing_service import PILOT_LIMITS, PLAN_CATALOG
from app.services.usage_service import current_period_key

PAID_PLANS = {SubscriptionPlan.STARTER.value, SubscriptionPlan.GROWTH.value, SubscriptionPlan.PRO.value}

# Never sent to the browser, even to a platform admin - the email_token is
# what authorizes cancelling a customer's recurring Paystack billing.
SECRET_SUBSCRIPTION_FIELDS = {"paystack_email_token", "paystack_authorization_code"}

NEAR_LIMIT_RATIO = 0.8


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def audit_log_ref(db: Client):
    return db.collection("admin_audit_log")


def record_audit(
    db: Client, admin: dict, *, action: str, org_id: str | None = None, target_uid: str | None = None,
    reason: str, before: dict | None = None, after: dict | None = None,
) -> None:
    audit_log_ref(db).document().set(
        {
            "action": action,
            "org_id": org_id,
            "target_uid": target_uid,
            "reason": reason,
            "before": before,
            "after": after,
            "admin_uid": admin["uid"],
            "admin_email": admin.get("email"),
            "created_at": _iso(_now()),
        }
    )


def list_audit_log(db: Client, *, limit: int = 100, org_id: str | None = None) -> list[dict]:
    # Over-fetch then filter, rather than where(org_id) + order_by, which
    # would need a composite index just for this screen.
    docs = audit_log_ref(db).order_by("created_at", direction=Query.DESCENDING).limit(500 if org_id else limit).stream()
    entries = [{"id": d.id, **d.to_dict()} for d in docs]
    if org_id:
        entries = [e for e in entries if e.get("org_id") == org_id][:limit]
    return entries


def _org_of_member(snap) -> str:
    # organizations/{org}/members/{uid}
    return snap.reference.parent.parent.id


def _org_of_house(snap) -> str:
    # organizations/{org}/farms/{farm}/houses/{house}
    return snap.reference.parent.parent.parent.parent.id


def _org_of_check(snap) -> str:
    # organizations/{org}/farms/{farm}/houses/{house}/flock_checks/{check}
    return snap.reference.parent.parent.parent.parent.parent.parent.id


def build_platform_snapshot(db: Client) -> dict[str, dict]:
    """One summary row per organization, keyed by org_id."""
    now = _now()
    cutoff_7d = _iso(now - timedelta(days=7))
    cutoff_30d = _iso(now - timedelta(days=30))
    period = current_period_key()

    orgs: dict[str, dict] = defaultdict(
        lambda: {
            "members": [],
            "pending_invites": 0,
            "farms": [],
            "houses": 0,
            "subscription": None,
            "ai_requests_month": 0,
            "open_alerts": 0,
            "critical_open_alerts": 0,
            "checks_7d": 0,
            "checks_30d": 0,
            "last_check_at": None,
            "platform_status": "active",
        }
    )

    for snap in db.collection_group("members").stream():
        orgs[_org_of_member(snap)]["members"].append({"id": snap.id, **snap.to_dict()})

    for snap in db.collection_group("invitations").stream():
        if snap.to_dict().get("status") == "pending":
            orgs[_org_of_member(snap)]["pending_invites"] += 1

    for snap in db.collection_group("farms").stream():
        data = snap.to_dict()
        orgs[_org_of_member(snap)]["farms"].append(
            {"id": snap.id, "name": data.get("name"), "country": data.get("country"), "archived": data.get("archived", False)}
        )

    for snap in db.collection_group("houses").stream():
        orgs[_org_of_house(snap)]["houses"] += 1

    for snap in db.collection_group("subscription").stream():
        if snap.id == "current":
            orgs[_org_of_member(snap)]["subscription"] = snap.to_dict()

    for snap in db.collection_group("usage_periods").stream():
        if snap.id == period:
            orgs[_org_of_member(snap)]["ai_requests_month"] = snap.to_dict().get("ai_requests", 0)

    for snap in db.collection_group("alerts").stream():
        data = snap.to_dict()
        if not data.get("resolved"):
            row = orgs[_org_of_member(snap)]
            row["open_alerts"] += 1
            if data.get("status") == "critical":
                row["critical_open_alerts"] += 1

    for snap in db.collection_group("flock_checks").stream():
        recorded_at = snap.to_dict().get("recorded_at")
        if not recorded_at:
            continue
        row = orgs[_org_of_check(snap)]
        if recorded_at >= cutoff_30d:
            row["checks_30d"] += 1
        if recorded_at >= cutoff_7d:
            row["checks_7d"] += 1
        if row["last_check_at"] is None or recorded_at > row["last_check_at"]:
            row["last_check_at"] = recorded_at

    # Org documents only exist once an admin has suspended/reactivated one.
    for snap in db.collection("organizations").stream():
        if snap.id in orgs:
            orgs[snap.id]["platform_status"] = (snap.to_dict() or {}).get("platform_status", "active")

    summaries = {org_id: _summarize(org_id, raw) for org_id, raw in orgs.items()}
    _fill_owners_from_firebase(summaries)
    return {org_id: _with_paying(org) for org_id, org in summaries.items()}


def _fill_owners_from_firebase(summaries: dict[str, dict]) -> None:
    """Owners whose OWNER membership was never backfilled (they've never
    opened Team/Settings/Billing - see membership_service) have no members
    doc, but their org_id IS their Firebase uid, so the account itself
    still says who they are and when they signed up."""
    missing = [org_id for org_id, org in summaries.items() if not org["owner_email"]]
    for start in range(0, len(missing), 100):  # get_users' batch limit
        try:
            result = firebase_auth.get_users([firebase_auth.UidIdentifier(uid) for uid in missing[start : start + 100]])
        except Exception:  # noqa: BLE001 - best-effort enrichment only
            return
        for record in result.users:
            org = summaries[record.uid]
            org["owner_email"] = record.email
            org["owner_name"] = record.display_name
            created = record.user_metadata.creation_timestamp if record.user_metadata else None
            if not org["created_at"] and created:
                org["created_at"] = datetime.fromtimestamp(created / 1000, tz=timezone.utc).isoformat()


def _summarize(org_id: str, raw: dict) -> dict:
    members = raw["members"]
    owner = next((m for m in members if m.get("role") == "owner" and m.get("id") == org_id), None) or next(
        (m for m in members if m.get("role") == "owner"), None
    )
    subscription = raw["subscription"] or {}
    plan = subscription.get("plan", SubscriptionPlan.PILOT.value)
    limits = subscription.get("limits") or PILOT_LIMITS
    joined = [m.get("joined_at") for m in members if m.get("joined_at")]
    ai_limit = limits.get("ai_requests_monthly")
    house_limit = limits.get("houses")

    return {
        "org_id": org_id,
        "owner_email": owner.get("email") if owner else None,
        "owner_name": owner.get("display_name") if owner else None,
        "created_at": min(joined) if joined else subscription.get("started_at"),
        "members_active": sum(1 for m in members if m.get("status") == "active"),
        "pending_invites": raw["pending_invites"],
        "farms": raw["farms"],
        "farm_count": len(raw["farms"]),
        "houses": raw["houses"],
        "plan": plan,
        "subscription_status": subscription.get("status", "active"),
        "price_ghs": subscription.get("price_ghs", 0) or 0,
        "comped": bool(subscription.get("comped")),
        # A paid plan set by an admin override has a price but no Paystack
        # billing behind it - only a real Paystack customer actually pays.
        "billed_via_paystack": bool(subscription.get("paystack_customer_code")),
        "limits": limits,
        "ai_requests_month": raw["ai_requests_month"],
        "ai_usage_ratio": (raw["ai_requests_month"] / ai_limit) if ai_limit else None,
        "house_usage_ratio": (raw["houses"] / house_limit) if house_limit else None,
        "open_alerts": raw["open_alerts"],
        "critical_open_alerts": raw["critical_open_alerts"],
        "checks_7d": raw["checks_7d"],
        "checks_30d": raw["checks_30d"],
        "last_check_at": raw["last_check_at"],
        "platform_status": raw["platform_status"],
    }


def _with_paying(org: dict) -> dict:
    return {**org, "paying": is_paying(org)}


def is_paying(org: dict) -> bool:
    return (
        org["plan"] in PAID_PLANS
        and org["subscription_status"] == "active"
        and org["billed_via_paystack"]
        and not org["comped"]
        and org["platform_status"] != "suspended"
    )


def build_overview(db: Client) -> dict:
    snapshot = build_platform_snapshot(db)
    orgs = list(snapshot.values())
    now = _now()

    # Checks-per-day for the activity chart (last 14 days, UTC).
    days = [(now - timedelta(days=i)).date().isoformat() for i in range(13, -1, -1)]
    checks_by_day = Counter()
    cutoff = days[0]
    for snap in db.collection_group("flock_checks").stream():
        day = (snap.to_dict().get("recorded_at") or "")[:10]
        if day >= cutoff:
            checks_by_day[day] += 1

    months = []
    cursor = now.replace(day=1)
    for _ in range(6):
        months.append(cursor.strftime("%Y-%m"))
        cursor = (cursor - timedelta(days=1)).replace(day=1)
    months.reverse()
    signups_by_month = Counter((o["created_at"] or "")[:7] for o in orgs)

    paying = [o for o in orgs if o["paying"]]
    near_limit = [
        o for o in orgs
        if (o["ai_usage_ratio"] or 0) >= NEAR_LIMIT_RATIO or (o["house_usage_ratio"] or 0) >= NEAR_LIMIT_RATIO
    ]

    return {
        "totals": {
            "organizations": len(orgs),
            "active_orgs_7d": sum(1 for o in orgs if o["checks_7d"] > 0),
            "farms": sum(o["farm_count"] for o in orgs),
            "houses": sum(o["houses"] for o in orgs),
            "members": sum(o["members_active"] for o in orgs),
            "paying_orgs": len(paying),
            "mrr_ghs": sum(o["price_ghs"] for o in paying),
            "ai_requests_month": sum(o["ai_requests_month"] for o in orgs),
            "open_alerts": sum(o["open_alerts"] for o in orgs),
            "critical_open_alerts": sum(o["critical_open_alerts"] for o in orgs),
            "checks_7d": sum(o["checks_7d"] for o in orgs),
            "suspended_orgs": sum(1 for o in orgs if o["platform_status"] == "suspended"),
        },
        "plan_distribution": dict(Counter(o["plan"] for o in orgs)),
        "signups_by_month": [{"month": m, "count": signups_by_month.get(m, 0)} for m in months],
        "checks_by_day": [{"day": d, "count": checks_by_day.get(d, 0)} for d in days],
        "recent_signups": sorted(orgs, key=lambda o: o["created_at"] or "", reverse=True)[:5],
        "near_limit": sorted(
            near_limit, key=lambda o: max(o["ai_usage_ratio"] or 0, o["house_usage_ratio"] or 0), reverse=True
        )[:10],
    }


def get_org_summary_or_404(db: Client, org_id: str) -> dict:
    org = build_platform_snapshot(db).get(org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org


def public_subscription(subscription: dict) -> dict:
    return {k: v for k, v in subscription.items() if k not in SECRET_SUBSCRIPTION_FIELDS}


def build_ai_usage(db: Client) -> dict:
    snapshot = build_platform_snapshot(db)
    period = current_period_key()

    totals_by_period = Counter()
    for snap in db.collection_group("usage_periods").stream():
        totals_by_period[snap.id] += snap.to_dict().get("ai_requests", 0)

    runs_by_status = Counter()
    runs_by_skill = Counter()
    runs_by_org = Counter()
    for snap in db.collection_group("agent_runs").stream():
        data = snap.to_dict()
        if not (data.get("created_at") or "").startswith(period):
            continue
        runs_by_status[data.get("status") or "unknown"] += 1
        runs_by_skill[data.get("skill") or "unknown"] += 1
        runs_by_org[_org_of_member(snap)] += 1

    rows = sorted(
        (
            {
                "org_id": o["org_id"],
                "owner_email": o["owner_email"],
                "farm_name": o["farms"][0]["name"] if o["farms"] else None,
                "plan": o["plan"],
                "ai_requests_month": o["ai_requests_month"],
                "ai_limit": o["limits"].get("ai_requests_monthly"),
                "ai_usage_ratio": o["ai_usage_ratio"],
                "agent_runs_month": runs_by_org.get(o["org_id"], 0),
            }
            for o in snapshot.values()
        ),
        key=lambda r: r["ai_requests_month"],
        reverse=True,
    )

    return {
        "period": period,
        "total_requests_month": totals_by_period.get(period, 0),
        "requests_by_period": [{"period": p, "count": c} for p, c in sorted(totals_by_period.items())][-6:],
        "agent_runs_by_status": dict(runs_by_status),
        "agent_runs_by_skill": dict(runs_by_skill),
        "orgs": rows,
    }


def all_members(db: Client) -> list[dict]:
    members = []
    for snap in db.collection_group("members").stream():
        data = snap.to_dict()
        members.append(
            {
                "uid": snap.id,
                "org_id": _org_of_member(snap),
                "email": data.get("email"),
                "display_name": data.get("display_name"),
                "role": data.get("role"),
                "status": data.get("status"),
                "joined_at": data.get("joined_at"),
            }
        )
    return members


def farm_names_by_org(db: Client) -> dict[str, str]:
    names: dict[str, str] = {}
    for snap in db.collection_group("farms").stream():
        name = snap.to_dict().get("name")
        if name:
            names.setdefault(_org_of_member(snap), name)
    return names


def search_users(db: Client, query: str | None) -> list[dict]:
    needle = (query or "").strip().lower()
    users = [
        u for u in all_members(db)
        if not needle or needle in f"{u['email'] or ''} {u['display_name'] or ''} {u['uid']}".lower()
    ]
    users.sort(key=lambda u: u["joined_at"] or "", reverse=True)
    users = users[:200]
    activity = load_activity(db)
    since_30 = (_now() - timedelta(days=29)).date().isoformat()
    for u in users:
        row = activity.get(u["uid"]) or {}
        u["last_seen_at"] = row.get("last_seen_at")
        u["days_active_30d"] = days_active(row, since_day=since_30)
    return users


def firebase_account_state(uid: str) -> dict:
    """Best-effort: a uid whose Firebase account was deleted outright
    still has a membership doc, which shouldn't break the org page."""
    try:
        record = firebase_auth.get_user(uid)
    except Exception:  # noqa: BLE001
        return {"exists": False, "disabled": None, "last_sign_in_at": None, "email_verified": None}
    last_sign_in = record.user_metadata.last_sign_in_timestamp if record.user_metadata else None
    return {
        "exists": True,
        "disabled": record.disabled,
        "email_verified": record.email_verified,
        "last_sign_in_at": (
            datetime.fromtimestamp(last_sign_in / 1000, tz=timezone.utc).isoformat() if last_sign_in else None
        ),
    }


def set_account_disabled(uid: str, disabled: bool) -> None:
    """Disabling also revokes refresh tokens so the person can't mint a new
    ID token. Their CURRENT token stays valid until it expires (up to ~1h),
    because get_current_user doesn't pass check_revoked=True."""
    try:
        firebase_auth.update_user(uid, disabled=disabled)
        if disabled:
            firebase_auth.revoke_refresh_tokens(uid)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail="Could not update this account in Firebase Auth") from exc


def set_org_suspended(db: Client, org_id: str, suspended: bool) -> list[str]:
    """Suspension = mark the org + disable every active member's login.
    Returns the uids whose accounts were changed."""
    uids = [d.id for d in members_ref(db, org_id).stream() if d.to_dict().get("status") == "active"]
    for uid in uids:
        set_account_disabled(uid, suspended)
    organization_ref(db, org_id).set(
        {"platform_status": "suspended" if suspended else "active", "platform_status_updated_at": _iso(_now())},
        merge=True,
    )
    return uids


def plan_override_update(plan: str, *, comped: bool, limits_override: dict | None, admin: dict, reason: str) -> dict:
    if plan == SubscriptionPlan.PILOT.value:
        base_limits, price = PILOT_LIMITS, 0
    elif plan in PLAN_CATALOG:
        base_limits, price = PLAN_CATALOG[plan]["limits"], PLAN_CATALOG[plan]["price_ghs"]
    else:  # enterprise - negotiated, so the limits must come from the admin
        if not limits_override:
            raise HTTPException(status_code=422, detail="Enterprise plans need explicit limits")
        base_limits, price = {}, 0

    return {
        "plan": plan,
        "status": "active",
        "limits": {**base_limits, **(limits_override or {})},
        "price_ghs": 0 if comped else price,
        "comped": comped,
        "admin_override": {"by": admin.get("email") or admin["uid"], "at": _iso(_now()), "reason": reason},
        "updated_at": _iso(_now()),
    }
