"""Platform admin console - FlockGuard's own operator view across every
organization. Gated by the `platform_admin` custom claim
(app/core/admin_auth.py), NOT by org roles: an org OWNER has no access here,
and a platform admin needs no membership in the orgs they look at.

Every write records an entry in `admin_audit_log` with the admin, the
reason they gave, and the before/after values.
"""

from fastapi import APIRouter, Depends, HTTPException, Query as QueryParam
from google.cloud.firestore import Client, Query

from app.core.admin_auth import require_platform_admin
from app.core.firestore import get_firestore_client
from app.core.refs import agent_runs_ref, alerts_ref, houses_ref, members_ref, subscription_ref
from app.models.schemas import AdminActionRequest, AdminPlanOverride, EnterpriseLeadUpdate, UpgradeOfferRequest
from app.services import (
    activity_service,
    admin_service,
    briefing_service,
    email_catalog,
    enterprise_service,
    upgrade_offer_service,
)
from app.services.email_service import send_upgrade_offer_email
from app.services.billing_service import get_or_create_subscription
from app.services.usage_service import count_birds, get_storage_bytes

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/me")
def admin_me(admin: dict = Depends(require_platform_admin)):
    return {"uid": admin["uid"], "email": admin.get("email"), "platform_admin": True}


@router.get("/overview")
def overview(_: dict = Depends(require_platform_admin), db: Client = Depends(get_firestore_client)):
    return admin_service.build_overview(db)


@router.get("/orgs")
def list_orgs(_: dict = Depends(require_platform_admin), db: Client = Depends(get_firestore_client)):
    orgs = admin_service.build_platform_snapshot(db).values()
    return sorted(orgs, key=lambda o: o["created_at"] or "", reverse=True)


@router.get("/orgs/{org_id}")
def get_org(org_id: str, _: dict = Depends(require_platform_admin), db: Client = Depends(get_firestore_client)):
    org = admin_service.get_org_summary_or_404(db, org_id)

    activity_rows = activity_service.load_activity(db)
    members = []
    for snap in members_ref(db, org_id).stream():
        members.append(
            {
                "id": snap.id,
                **snap.to_dict(),
                "account": admin_service.firebase_account_state(snap.id),
                "last_seen_at": (activity_rows.get(snap.id) or {}).get("last_seen_at"),
            }
        )

    farms = []
    for farm in org["farms"]:
        houses = [{"id": h.id, **h.to_dict()} for h in houses_ref(db, org_id, farm["id"]).stream()]
        farms.append({**farm, "houses": houses})

    alerts = alerts_ref(db, org_id).order_by("created_at", direction=Query.DESCENDING).limit(10).stream()
    runs = agent_runs_ref(db, org_id).order_by("created_at", direction=Query.DESCENDING).limit(10).stream()

    return {
        **org,
        "farms": farms,
        "members": members,
        "subscription": admin_service.public_subscription(get_or_create_subscription(db, org_id)),
        "usage": {
            "birds": count_birds(db, org_id),
            "storage_mb": round(get_storage_bytes(db, org_id) / (1024 * 1024), 1),
        },
        "recent_alerts": [{"id": a.id, **a.to_dict()} for a in alerts],
        "recent_agent_runs": [
            {k: v for k, v in {"id": r.id, **r.to_dict()}.items() if k not in {"tool_calls", "rag_sources_used"}}
            for r in runs
        ],
        "audit_log": admin_service.list_audit_log(db, org_id=org_id, limit=20),
        "upgrade_offer": upgrade_offer_service.get_offer(db, org_id),
    }


@router.patch("/orgs/{org_id}/subscription")
def override_subscription(
    org_id: str,
    payload: AdminPlanOverride,
    admin: dict = Depends(require_platform_admin),
    db: Client = Depends(get_firestore_client),
):
    """Manual plan change (comp, pilot extension, enterprise deal). Does NOT
    touch Paystack: if the org also has a live Paystack subscription, its
    next webhook can still move the plan - cancel it in Paystack first."""
    admin_service.get_org_summary_or_404(db, org_id)
    before = admin_service.public_subscription(get_or_create_subscription(db, org_id))
    update = admin_service.plan_override_update(
        payload.plan.value,
        comped=payload.comped,
        limits_override=payload.limits,
        admin=admin,
        reason=payload.reason,
    )
    doc_ref = subscription_ref(db, org_id)
    doc_ref.set(update, merge=True)
    after = admin_service.public_subscription(doc_ref.get().to_dict())
    admin_service.record_audit(
        db, admin, action="subscription.override", org_id=org_id, reason=payload.reason,
        before={k: before.get(k) for k in ("plan", "limits", "price_ghs", "comped")},
        after={k: after.get(k) for k in ("plan", "limits", "price_ghs", "comped")},
    )
    return after


@router.post("/orgs/{org_id}/suspend")
def suspend_org(
    org_id: str,
    payload: AdminActionRequest,
    admin: dict = Depends(require_platform_admin),
    db: Client = Depends(get_firestore_client),
):
    org = admin_service.get_org_summary_or_404(db, org_id)
    if org["platform_status"] == "suspended":
        raise HTTPException(status_code=409, detail="Organization is already suspended")
    if members_ref(db, org_id).document(admin["uid"]).get().exists:
        raise HTTPException(status_code=400, detail="You can't suspend an organization you belong to")
    uids = admin_service.set_org_suspended(db, org_id, True)
    admin_service.record_audit(
        db, admin, action="org.suspend", org_id=org_id, reason=payload.reason,
        before={"platform_status": "active"}, after={"platform_status": "suspended", "disabled_uids": uids},
    )
    return {"org_id": org_id, "platform_status": "suspended", "disabled_accounts": len(uids)}


@router.post("/orgs/{org_id}/reactivate")
def reactivate_org(
    org_id: str,
    payload: AdminActionRequest,
    admin: dict = Depends(require_platform_admin),
    db: Client = Depends(get_firestore_client),
):
    org = admin_service.get_org_summary_or_404(db, org_id)
    if org["platform_status"] != "suspended":
        raise HTTPException(status_code=409, detail="Organization is not suspended")
    uids = admin_service.set_org_suspended(db, org_id, False)
    admin_service.record_audit(
        db, admin, action="org.reactivate", org_id=org_id, reason=payload.reason,
        before={"platform_status": "suspended"}, after={"platform_status": "active", "enabled_uids": uids},
    )
    return {"org_id": org_id, "platform_status": "active", "enabled_accounts": len(uids)}


@router.get("/users")
def search_users(
    q: str | None = None,
    _: dict = Depends(require_platform_admin),
    db: Client = Depends(get_firestore_client),
):
    return admin_service.search_users(db, q)


def _set_user_disabled(uid: str, disabled: bool, payload: AdminActionRequest, admin: dict, db: Client) -> dict:
    if uid == admin["uid"]:
        raise HTTPException(status_code=400, detail="You can't change your own account here")
    memberships = [u for u in admin_service.search_users(db, uid) if u["uid"] == uid]
    admin_service.set_account_disabled(uid, disabled)
    admin_service.record_audit(
        db, admin, action="user.disable" if disabled else "user.enable",
        org_id=memberships[0]["org_id"] if memberships else None, target_uid=uid, reason=payload.reason,
        before={"disabled": not disabled}, after={"disabled": disabled},
    )
    return {"uid": uid, "disabled": disabled}


@router.post("/users/{uid}/disable")
def disable_user(
    uid: str,
    payload: AdminActionRequest,
    admin: dict = Depends(require_platform_admin),
    db: Client = Depends(get_firestore_client),
):
    return _set_user_disabled(uid, True, payload, admin, db)


@router.post("/users/{uid}/enable")
def enable_user(
    uid: str,
    payload: AdminActionRequest,
    admin: dict = Depends(require_platform_admin),
    db: Client = Depends(get_firestore_client),
):
    return _set_user_disabled(uid, False, payload, admin, db)


@router.get("/ai-usage")
def ai_usage(_: dict = Depends(require_platform_admin), db: Client = Depends(get_firestore_client)):
    return admin_service.build_ai_usage(db)


@router.get("/audit-log")
def audit_log(
    limit: int = QueryParam(100, ge=1, le=500),
    org_id: str | None = None,
    _: dict = Depends(require_platform_admin),
    db: Client = Depends(get_firestore_client),
):
    return admin_service.list_audit_log(db, limit=limit, org_id=org_id)


@router.get("/activity")
def activity(_: dict = Depends(require_platform_admin), db: Client = Depends(get_firestore_client)):
    """Online now, DAU/WAU/MAU, the 30-day active-users chart and dormant
    users - see app/services/activity_service.py."""
    data = activity_service.build_activity(db, admin_service.all_members(db))
    farm_names = admin_service.farm_names_by_org(db)
    for key in ("online", "recent", "dormant"):
        for person in data[key]:
            person["farm_name"] = farm_names.get(person["org_id"])
    return data


@router.get("/enterprise")
def enterprise(_: dict = Depends(require_platform_admin), db: Client = Depends(get_firestore_client)):
    """Every Enterprise request plus the orgs worth offering it to."""
    leads = enterprise_service.list_requests(db)
    open_org_ids = {lead["org_id"] for lead in leads if lead.get("status") in enterprise_service.OPEN_STATUSES}
    orgs = list(admin_service.build_platform_snapshot(db).values())
    by_org = {o["org_id"]: o for o in orgs}
    for lead in leads:
        org = by_org.get(lead["org_id"])
        lead["org_plan_now"] = org["plan"] if org else None
    return {
        "leads": leads,
        "counts": {s: sum(1 for lead in leads if lead.get("status") == s) for s in ("new", "contacted", "won", "lost")},
        "candidates": enterprise_service.build_upgrade_candidates(orgs, open_org_ids),
    }


@router.patch("/enterprise/{request_id}")
def update_enterprise_lead(
    request_id: str,
    payload: EnterpriseLeadUpdate,
    admin: dict = Depends(require_platform_admin),
    db: Client = Depends(get_firestore_client),
):
    if payload.status is None and payload.note is None:
        raise HTTPException(status_code=422, detail="Nothing to update")
    before, after = enterprise_service.update_request(
        db, request_id, status=payload.status.value if payload.status else None, note=payload.note, admin=admin
    )
    if payload.status and payload.status.value != before.get("status"):
        admin_service.record_audit(
            db, admin, action="enterprise.status", org_id=before["org_id"],
            reason=payload.note or f"Marked {payload.status.value}",
            before={"status": before.get("status")}, after={"status": payload.status.value},
        )
    return after


@router.get("/emails")
def emails(_: dict = Depends(require_platform_admin), db: Client = Depends(get_firestore_client)):
    """Every email FlockGuard sends - when, to whom, whether it can go out
    right now, and a preview of exactly what recipients get."""
    return email_catalog.build_catalog(db)


@router.post("/emails/{key}/test")
async def send_test_email(key: str, admin: dict = Depends(require_platform_admin)):
    """Sends a sample of one email to the signed-in admin's own address -
    never to anyone else."""
    if key not in email_catalog.TEMPLATES:
        raise HTTPException(status_code=404, detail="Unknown email")
    to_email = admin.get("email")
    if not to_email:
        raise HTTPException(status_code=400, detail="Your account has no email address to send the test to")
    sent = await email_catalog.send_test(key, to_email)
    if not sent:
        raise HTTPException(
            status_code=502,
            detail="The email could not be sent - check the SMTP settings and the backend log for the reason.",
        )
    return {"sent": True, "to": to_email}


@router.get("/briefing")
def briefing(_: dict = Depends(require_platform_admin), db: Client = Depends(get_firestore_client)):
    """This week vs last, what needs an admin's attention, and a one-line
    summary of every farmer - see app/services/briefing_service.py."""
    return briefing_service.build_briefing(db)


@router.post("/orgs/{org_id}/upgrade-offer")
async def offer_upgrade(
    org_id: str,
    payload: UpgradeOfferRequest,
    admin: dict = Depends(require_platform_admin),
    db: Client = Depends(get_firestore_client),
):
    """Suggests a paid plan to the org's owner (email + in-app banner). Unlike
    PATCH /subscription, nothing changes until THEY upgrade and pay."""
    org = admin_service.get_org_summary_or_404(db, org_id)
    offer = upgrade_offer_service.create_offer(db, org_id, plan=payload.plan, message=payload.message, admin=admin)
    email_sent = False
    if org["owner_email"]:
        email_sent = await send_upgrade_offer_email(
            to_email=org["owner_email"],
            farm_name=(org["farms"][0]["name"] if org["farms"] else None) or "your farm",
            plan=payload.plan,
            price_ghs=offer["price_ghs"],
            limits=offer["limits"],
            message=payload.message,
        )
        if email_sent:
            upgrade_offer_service.mark_email_sent(db, org_id)
    admin_service.record_audit(
        db, admin, action="upgrade.offer", org_id=org_id, reason=payload.message or f"Offered {payload.plan}",
        before={"plan": offer["current_plan"]}, after={"offered_plan": payload.plan, "email_sent": email_sent},
    )
    return {**upgrade_offer_service.get_offer(db, org_id), "email_sent": email_sent}


@router.delete("/orgs/{org_id}/upgrade-offer")
def withdraw_upgrade_offer(
    org_id: str,
    admin: dict = Depends(require_platform_admin),
    db: Client = Depends(get_firestore_client),
):
    offer = upgrade_offer_service.set_status(db, org_id, "withdrawn")
    if offer is None:
        raise HTTPException(status_code=404, detail="No upgrade offer for this organization")
    admin_service.record_audit(
        db, admin, action="upgrade.withdraw", org_id=org_id, reason=f"Withdrew {offer['plan']} offer",
        before={"offered_plan": offer["plan"]}, after=None,
    )
    return offer

