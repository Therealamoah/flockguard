"""The admin console's Summary page (GET /admin/briefing): how the week went,
what needs an admin's attention, and a one-line summary of every farmer.

Everything is derived from data the platform already records - the
per-org snapshot (admin_service.build_platform_snapshot), activity
heartbeats (activity_service), alerts, flock checks and Enterprise
requests - using plain, explainable rules, so every flag says exactly why
it was raised.
"""

from collections import defaultdict
from datetime import datetime, timedelta, timezone

from google.cloud.firestore import Client

from app.services import activity_service, admin_service, enterprise_service

STUCK_SETUP_AFTER = timedelta(days=3)
STALE_CRITICAL_AFTER = timedelta(hours=24)

# Farmer stages, roughly in order of how much they need attention.
STAGES = {
    "suspended": "Suspended",
    "payment_issue": "Payment issue",
    "health_risk": "Flock health risk",
    "inactive": "Gone quiet",
    "slipping": "Slipping",
    "setting_up": "Setting up",
    "active": "Active",
}
STAGE_ORDER = list(STAGES)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _org_name(org: dict) -> str:
    return (org["farms"][0]["name"] if org["farms"] else None) or org["owner_email"] or org["org_id"]


def _stage(org: dict, now: datetime) -> tuple[str, str]:
    """(stage key, plain-English reason)."""
    if org["platform_status"] == "suspended":
        return "suspended", "Suspended by an admin."
    if org["subscription_status"] == "past_due":
        return "payment_issue", f"Last payment for the {org['plan']} plan failed."
    if org["critical_open_alerts"]:
        n = org["critical_open_alerts"]
        return "health_risk", f"{n} critical alert{'s' if n > 1 else ''} open on their farm."
    if org["farm_count"] == 0 or org["houses"] == 0:
        what = "a farm" if org["farm_count"] == 0 else "a house"
        return "setting_up", f"Signed up but hasn't added {what} yet."
    if org["checks_30d"] == 0:
        if org["last_check_at"]:
            return "inactive", "No flock checks in over 30 days."
        return "setting_up", "Has houses but hasn't logged a flock check yet."
    if org["checks_7d"] == 0:
        return "slipping", "Checked in this month, but not in the last 7 days."
    return "active", f"{org['checks_7d']} flock check{'s' if org['checks_7d'] != 1 else ''} this week."


def build_briefing(db: Client) -> dict:
    now = _now()
    week_ago, two_weeks_ago = now - timedelta(days=7), now - timedelta(days=14)
    snapshot = admin_service.build_platform_snapshot(db)
    activity = activity_service.load_activity(db)
    leads = enterprise_service.list_requests(db)

    # Last time anyone in each org opened the app.
    last_seen_by_org: dict[str, str] = {}
    for row in activity.values():
        org_id, seen = row.get("org_id"), row.get("last_seen_at")
        if org_id and seen and seen > last_seen_by_org.get(org_id, ""):
            last_seen_by_org[org_id] = seen

    # Week-over-week counts.
    checks_this_week = checks_last_week = 0
    for snap in db.collection_group("flock_checks").stream():
        at = snap.to_dict().get("recorded_at") or ""
        if at >= _iso(week_ago):
            checks_this_week += 1
        elif at >= _iso(two_weeks_ago):
            checks_last_week += 1

    alerts_this_week = alerts_last_week = 0
    stale_critical = defaultdict(list)  # org_id -> [created_at]
    for snap in db.collection_group("alerts").stream():
        data = snap.to_dict()
        at = data.get("created_at") or ""
        if at >= _iso(week_ago):
            alerts_this_week += 1
        elif at >= _iso(two_weeks_ago):
            alerts_last_week += 1
        if data.get("status") == "critical" and not data.get("resolved") and at and at < _iso(now - STALE_CRITICAL_AFTER):
            stale_critical[snap.reference.parent.parent.id].append(at)

    orgs = list(snapshot.values())
    signups_this_week = sum(1 for o in orgs if (o["created_at"] or "") >= _iso(week_ago))
    signups_last_week = sum(1 for o in orgs if _iso(two_weeks_ago) <= (o["created_at"] or "") < _iso(week_ago))

    since_7 = (now.date() - timedelta(days=6)).isoformat()
    since_14 = (now.date() - timedelta(days=13)).isoformat()
    active_users_this_week = sum(1 for r in activity.values() if any(d >= since_7 for d in r.get("active_days", [])))
    active_users_last_week = sum(
        1 for r in activity.values() if any(since_14 <= d < since_7 for d in r.get("active_days", []))
    )

    # --- farmer summaries -------------------------------------------------
    farmers = []
    for o in orgs:
        stage, reason = _stage(o, now)
        farmers.append(
            {
                "org_id": o["org_id"],
                "name": _org_name(o),
                "owner_email": o["owner_email"],
                "owner_name": o["owner_name"],
                "plan": o["plan"],
                "comped": o["comped"],
                "stage": stage,
                "stage_label": STAGES[stage],
                "reason": reason,
                "farms": o["farm_count"],
                "houses": o["houses"],
                "members": o["members_active"],
                "checks_7d": o["checks_7d"],
                "checks_30d": o["checks_30d"],
                "last_check_at": o["last_check_at"],
                "last_seen_at": last_seen_by_org.get(o["org_id"]),
                "open_alerts": o["open_alerts"],
                "critical_open_alerts": o["critical_open_alerts"],
                "created_at": o["created_at"],
            }
        )
    farmers.sort(key=lambda f: (STAGE_ORDER.index(f["stage"]), f["name"].lower()))
    stage_counts = {key: sum(1 for f in farmers if f["stage"] == key) for key in STAGES}

    # --- needs attention --------------------------------------------------
    items = []
    by_id = {o["org_id"]: o for o in orgs}

    def item(severity, kind, title, detail, org_id=None, link=None):
        items.append(
            {"severity": severity, "kind": kind, "title": title, "detail": detail, "org_id": org_id,
             "link": link or (f"/admin/orgs/{org_id}" if org_id else None)}
        )

    for org_id, created in stale_critical.items():
        org = by_id.get(org_id)
        if not org:
            continue
        hours = int((now - datetime.fromisoformat(min(created))).total_seconds() // 3600)
        item("critical", "stale_critical", f"Critical alert unresolved for {hours}h",
             f"{_org_name(org)} has {len(created)} critical alert{'s' if len(created) > 1 else ''} open for over a day - "
             "consider reaching out.", org_id)

    for o in orgs:
        if o["subscription_status"] == "past_due":
            item("critical", "payment", "Payment failed",
                 f"{_org_name(o)}'s {o['plan']} payment failed - they may lose access.", o["org_id"])

    for lead in leads:
        if lead.get("status") == "new":
            wants = (lead.get("requested") or {}).get("houses") or "?"
            item("warning", "enterprise", "New Enterprise request",
                 f"{lead.get('farm_name') or lead.get('email')} wants {wants} houses - not contacted yet.",
                 lead.get("org_id"), "/admin/enterprise")

    for f in farmers:
        created = f["created_at"]
        if f["stage"] == "setting_up" and created and created < _iso(now - STUCK_SETUP_AFTER):
            days = (now - datetime.fromisoformat(created)).days
            item("warning", "stuck_setup", "Stuck in setup", f"{f['name']} joined {days} days ago. {f['reason']}",
                 f["org_id"])
        elif f["stage"] in ("slipping", "inactive"):
            item("info" if f["stage"] == "slipping" else "warning", "quiet", STAGES[f["stage"]],
                 f"{f['name']}: {f['reason']}", f["org_id"])

    for o in orgs:
        ratios = [r for r in (o["ai_usage_ratio"], o["house_usage_ratio"]) if r is not None]
        if ratios and max(ratios) >= 1:
            item("warning", "limit", "Hit a plan limit",
                 f"{_org_name(o)} is at {round(max(ratios) * 100)}% of a {o['plan']} limit - likely blocked.",
                 o["org_id"])
        elif ratios and max(ratios) >= admin_service.NEAR_LIMIT_RATIO:
            item("info", "limit", "Close to a plan limit",
                 f"{_org_name(o)} is at {round(max(ratios) * 100)}% of a {o['plan']} limit - upgrade opportunity.",
                 o["org_id"])

    rank = {"critical": 0, "warning": 1, "info": 2}
    items.sort(key=lambda i: rank[i["severity"]])

    return {
        "generated_at": _iso(now),
        "week": {
            "signups": {"this_week": signups_this_week, "last_week": signups_last_week},
            "active_users": {"this_week": active_users_this_week, "last_week": active_users_last_week},
            "flock_checks": {"this_week": checks_this_week, "last_week": checks_last_week},
            "alerts_raised": {"this_week": alerts_this_week, "last_week": alerts_last_week},
        },
        "attention": items,
        "stage_counts": stage_counts,
        "stage_labels": STAGES,
        "farmers": farmers,
    }
