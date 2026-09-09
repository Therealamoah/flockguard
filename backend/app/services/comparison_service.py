"""Structured Morning-vs-Evening (or Emergency) Flock Check comparison.

Pairs a later check against the same house's most recent MORNING check
recorded on the same calendar date, and computes a structured diff. This
is deliberately pure and deterministic - no AI involved, so it can be
persisted, tested, and trusted the same way the Risk Engine is.

Known simplification: "same calendar date" is computed in UTC, since Farm
documents don't carry a timezone today. Fine for a single-timezone pilot;
revisit (store a farm-level IANA timezone) if farms span multiple zones.
"""

from __future__ import annotations

from datetime import date, datetime, timezone


def _parse(ts: str) -> datetime:
    dt = datetime.fromisoformat(ts)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def find_check_for_period_on_date(
    checks: list[dict],
    period: str,
    target_date: date,
    *,
    before: datetime | None = None,
) -> dict | None:
    """Latest check of `period` recorded on `target_date` (UTC).

    `checks` need not be pre-filtered or pre-sorted. If `before` is given,
    only checks strictly earlier than it are considered (so a later check
    can't accidentally "compare against" a check that hasn't happened yet).
    """
    candidates = []
    for check in checks:
        recorded_at = check.get("recorded_at")
        if not recorded_at or check.get("period") != period:
            continue
        try:
            parsed = _parse(recorded_at)
        except (ValueError, TypeError):
            continue
        if parsed.astimezone(timezone.utc).date() != target_date:
            continue
        if before is not None and parsed >= before:
            continue
        candidates.append((parsed, check))

    if not candidates:
        return None
    return max(candidates, key=lambda pair: pair[0])[1]


def compare_checks(morning: dict, later: dict) -> dict:
    """Structured diff between a Morning Check and a later same-day check."""
    morning_mortality = morning.get("mortality") or 0
    later_mortality = later.get("mortality") or 0
    mortality_change = later_mortality - morning_mortality

    feed_change = None
    if later.get("feed_kg") is not None and morning.get("feed_kg") is not None:
        feed_change = round(later["feed_kg"] - morning["feed_kg"], 2)

    morning_risk = morning.get("risk_score") or 0
    later_risk = later.get("risk_score") or 0
    risk_change = later_risk - morning_risk

    water_changed = later.get("water_level") != morning.get("water_level")
    activity_changed = later.get("activity") != morning.get("activity")
    feeding_behaviour_changed = later.get("feeding_behaviour") != morning.get("feeding_behaviour")

    flags = []
    if mortality_change > 0:
        flags.append("mortality_increased")
    elif mortality_change < 0:
        flags.append("mortality_decreased")
    if feed_change is not None and feed_change < 0:
        flags.append("feed_decreased")
    elif feed_change is not None and feed_change and feed_change > 0:
        flags.append("feed_increased")
    if water_changed and later.get("water_level") == "lower":
        flags.append("water_worsened")
    if activity_changed and later.get("activity") in ("reduced", "lethargic"):
        flags.append("activity_worsened")
    if feeding_behaviour_changed and later.get("feeding_behaviour") in ("reduced", "none"):
        flags.append("feeding_worsened")
    if risk_change > 0:
        flags.append("risk_increased")
    elif risk_change < 0:
        flags.append("risk_decreased")

    return {
        "morning_check_id": morning.get("id"),
        "evening_check_id": later.get("id"),
        "morning_recorded_at": morning.get("recorded_at"),
        "evening_recorded_at": later.get("recorded_at"),
        "morning_risk_score": morning.get("risk_score"),
        "evening_risk_score": later.get("risk_score"),
        "risk_change": risk_change,
        "mortality_change": mortality_change,
        "feed_change": feed_change,
        "water_changed": water_changed,
        "activity_changed": activity_changed,
        "feeding_behaviour_changed": feeding_behaviour_changed,
        "summary_flags": flags,
    }


def build_morning_evening_comparison(recent_checks: list[dict], current_check: dict) -> dict | None:
    """Builds the comparison for `current_check` (an evening/emergency check)
    against that day's morning check, if one exists.

    `recent_checks` should be the house's recent checks (any order, may or
    may not include `current_check` itself - it's excluded by id). Returns
    None - never raises - when there is no morning check to compare
    against (including when `current_check` is itself a morning check).
    """
    if current_check.get("period") not in ("evening", "emergency"):
        return None
    recorded_at = current_check.get("recorded_at")
    if not recorded_at:
        return None

    try:
        current_dt = _parse(recorded_at)
    except (ValueError, TypeError):
        return None

    candidates = [c for c in recent_checks if c.get("id") != current_check.get("id")]
    morning = find_check_for_period_on_date(
        candidates,
        "morning",
        current_dt.astimezone(timezone.utc).date(),
        before=current_dt,
    )
    if not morning:
        return None
    return compare_checks(morning, current_check)
