"""Who is actually using FlockGuard - the data behind the admin console's
Activity page (app/api/routes/admin.py::activity).

Firebase's own `last_sign_in_timestamp` only moves when someone types their
password, and people stay signed in for weeks, so it can't answer "who used
the app today". Instead the farm app sends a heartbeat (POST
/activity/heartbeat) on load, on every page change and about once a minute
while the tab is visible, and each one lands in a single per-user document:

    user_activity/{uid} = {
        uid, email, display_name, org_id,
        first_seen_at, last_seen_at, last_path,
        active_days: ["2026-11-01", "2026-11-03", ...]   # UTC, newest last
    }

`active_days` (capped at ACTIVE_DAYS_KEPT) is what DAU/WAU/MAU, the 30-day
chart and "days active" are all computed from, so the whole Activity page is
one collection read with no indexes.

Writes are throttled per process (THROTTLE_SECONDS) so an open tab costs at
most one Firestore write every couple of minutes. The very first heartbeat
of a UTC day always writes, so the day is never missed.
"""

from datetime import datetime, timedelta, timezone
from threading import Lock

from google.cloud.firestore import Client

ONLINE_WINDOW = timedelta(minutes=5)
THROTTLE_SECONDS = 120
ACTIVE_DAYS_KEPT = 90
DORMANT_AFTER_DAYS = 14

# uid -> (last write as a unix timestamp, UTC day of that write)
_last_write: dict[str, tuple[float, str]] = {}
_lock = Lock()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def activity_ref(db: Client):
    return db.collection("user_activity")


def reset_throttle() -> None:
    """Tests only - each test gets a fresh in-memory Firestore."""
    with _lock:
        _last_write.clear()


def record_heartbeat(db: Client, user: dict, *, path: str | None = None, now: datetime | None = None) -> bool:
    """Returns whether anything was written (False = throttled)."""
    now = now or _now()
    uid = user["uid"]
    day = now.date().isoformat()
    ts = now.timestamp()

    with _lock:
        previous = _last_write.get(uid)
        if previous and previous[1] == day and ts - previous[0] < THROTTLE_SECONDS:
            return False
        _last_write[uid] = (ts, day)

    doc_ref = activity_ref(db).document(uid)
    first_write_today = previous is None or previous[1] != day
    existing = (doc_ref.get().to_dict() or {}) if first_write_today else None

    update = {
        "uid": uid,
        "email": user.get("email"),
        "org_id": user.get("org_id", uid),
        "last_seen_at": now.isoformat(),
    }
    if user.get("name"):
        update["display_name"] = user["name"]
    if path:
        update["last_path"] = path

    # Only read-modify-write `active_days` on the first write of a day (or
    # after a restart forgot the throttle) - every other heartbeat is a
    # blind merge of last_seen_at.
    if existing is not None:
        days = [d for d in existing.get("active_days", []) if d != day] + [day]
        update["active_days"] = days[-ACTIVE_DAYS_KEPT:]
        if not existing.get("first_seen_at"):
            update["first_seen_at"] = now.isoformat()

    doc_ref.set(update, merge=True)
    return True


def load_activity(db: Client) -> dict[str, dict]:
    return {snap.id: snap.to_dict() for snap in activity_ref(db).stream()}


def is_online(row: dict, now: datetime) -> bool:
    last = row.get("last_seen_at")
    return bool(last) and last >= (now - ONLINE_WINDOW).isoformat()


def days_active(row: dict, *, since_day: str) -> int:
    return sum(1 for d in row.get("active_days", []) if d >= since_day)


def build_activity(db: Client, members: list[dict], *, now: datetime | None = None) -> dict:
    """`members` are the platform's membership rows (admin_service.search_users
    shape: uid/org_id/email/display_name/role/joined_at), used to find people
    who signed up but never opened the app since tracking began."""
    now = now or _now()
    rows = load_activity(db)
    today = now.date()
    day_keys = [(today - timedelta(days=i)).isoformat() for i in range(29, -1, -1)]
    since_7 = (today - timedelta(days=6)).isoformat()
    since_30 = day_keys[0]
    dormant_cutoff = (now - timedelta(days=DORMANT_AFTER_DAYS)).isoformat()

    dau_by_day = {d: 0 for d in day_keys}
    for row in rows.values():
        for d in row.get("active_days", []):
            if d in dau_by_day:
                dau_by_day[d] += 1

    dau = dau_by_day[today.isoformat()]
    wau = sum(1 for r in rows.values() if days_active(r, since_day=since_7) > 0)
    mau = sum(1 for r in rows.values() if days_active(r, since_day=since_30) > 0)

    def person(uid: str, row: dict) -> dict:
        return {
            "uid": uid,
            "email": row.get("email"),
            "display_name": row.get("display_name"),
            "org_id": row.get("org_id"),
            "last_seen_at": row.get("last_seen_at"),
            "last_path": row.get("last_path"),
            "first_seen_at": row.get("first_seen_at"),
            "days_active_30d": days_active(row, since_day=since_30),
        }

    online = sorted(
        (person(uid, r) for uid, r in rows.items() if is_online(r, now)),
        key=lambda p: p["last_seen_at"],
        reverse=True,
    )
    recent = sorted(
        (person(uid, r) for uid, r in rows.items() if r.get("last_seen_at")),
        key=lambda p: p["last_seen_at"],
        reverse=True,
    )[:50]

    # Dormant = has a login but hasn't opened the app in DORMANT_AFTER_DAYS,
    # or has never opened it at all since tracking started.
    dormant = []
    seen_uids = set()
    for m in members:
        if m["uid"] in seen_uids or m.get("status") not in (None, "active"):
            continue
        seen_uids.add(m["uid"])
        row = rows.get(m["uid"])
        last = row.get("last_seen_at") if row else None
        if last and last >= dormant_cutoff:
            continue
        dormant.append(
            {
                "uid": m["uid"],
                "email": m.get("email"),
                "display_name": m.get("display_name"),
                "org_id": m["org_id"],
                "role": m.get("role"),
                "joined_at": m.get("joined_at"),
                "last_seen_at": last,
            }
        )
    dormant.sort(key=lambda p: p["last_seen_at"] or "", reverse=True)

    return {
        "generated_at": now.isoformat(),
        "online_window_minutes": int(ONLINE_WINDOW.total_seconds() // 60),
        "dormant_after_days": DORMANT_AFTER_DAYS,
        "totals": {
            "online_now": len(online),
            "dau": dau,
            "wau": wau,
            "mau": mau,
            "stickiness": (dau / mau) if mau else None,
            "tracked_users": len(rows),
            "dormant": len(dormant),
        },
        "dau_by_day": [{"day": d, "count": dau_by_day[d]} for d in day_keys],
        "online": online,
        "recent": recent,
        "dormant": dormant[:100],
    }
