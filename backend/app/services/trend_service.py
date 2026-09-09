"""Deterministic trend detection over a house's recent Flock Checks.

Pure Python pattern-matching, same philosophy as the Risk Engine: Grok is
never asked whether a numeric trend exists, only (optionally, elsewhere)
to help phrase one this module already found.
"""

from __future__ import annotations

CONSECUTIVE_WINDOW = 3


def _increasing_over_time(newest_first_values: list[float]) -> bool:
    """True if values strictly increase as time moves forward - i.e. strictly
    decrease across a newest-first list."""
    return len(newest_first_values) >= 2 and all(
        newest_first_values[i] > newest_first_values[i + 1] for i in range(len(newest_first_values) - 1)
    )


def _decreasing_over_time(newest_first_values: list[float]) -> bool:
    return len(newest_first_values) >= 2 and all(
        newest_first_values[i] < newest_first_values[i + 1] for i in range(len(newest_first_values) - 1)
    )


def _evidence(window: list[dict], *fields: str) -> list[dict]:
    return [
        {"check_id": c.get("id"), "recorded_at": c.get("recorded_at"), **{f: c.get(f) for f in fields}}
        for c in window
    ]


def detect_trends(house_id: str, house_name: str, recent_checks: list[dict]) -> list[dict]:
    """`recent_checks` must be newest-first. Returns zero or more structured
    insight dicts; never raises on missing or short data.
    """
    window = recent_checks[:CONSECUTIVE_WINDOW]
    insights: list[dict] = []
    if len(window) < CONSECUTIVE_WINDOW:
        return insights

    def _base(insight_type: str, severity: str, message_key: str, message: str, evidence: list[dict]) -> dict:
        return {
            "type": insight_type,
            "house_id": house_id,
            "house_name": house_name,
            "severity": severity,
            "message_key": message_key,
            "message": message,
            "evidence": evidence,
        }

    mortality = [c.get("mortality") for c in window if c.get("mortality") is not None]
    if len(mortality) == CONSECUTIVE_WINDOW and _increasing_over_time(mortality):
        insights.append(
            _base(
                "mortality_increase",
                "warning",
                "mortality_increased_three_checks",
                f"{house_name}: mortality has risen for {CONSECUTIVE_WINDOW} checks in a row.",
                _evidence(window, "mortality"),
            )
        )

    feed = [c.get("feed_kg") for c in window if c.get("feed_kg") is not None]
    if len(feed) == CONSECUTIVE_WINDOW and _decreasing_over_time(feed):
        insights.append(
            _base(
                "feed_decline",
                "watch",
                "feed_declined_three_checks",
                f"{house_name}: feed consumption has dropped for {CONSECUTIVE_WINDOW} checks in a row.",
                _evidence(window, "feed_kg"),
            )
        )

    risk = [c.get("risk_score") for c in window if c.get("risk_score") is not None]
    if len(risk) == CONSECUTIVE_WINDOW and _increasing_over_time(risk):
        insights.append(
            _base(
                "risk_increase",
                "warning",
                "risk_increased_three_checks",
                f"{house_name}: risk score has increased for {CONSECUTIVE_WINDOW} checks in a row.",
                _evidence(window, "risk_score"),
            )
        )

    if sum(1 for c in window if c.get("water_level") == "lower") == CONSECUTIVE_WINDOW:
        insights.append(
            _base(
                "water_low_repeated",
                "watch",
                "water_low_three_checks",
                f"{house_name}: water has been reported lower than usual for {CONSECUTIVE_WINDOW} checks in a row.",
                _evidence(window, "water_level"),
            )
        )

    if sum(1 for c in window if c.get("activity") in ("reduced", "lethargic")) == CONSECUTIVE_WINDOW:
        insights.append(
            _base(
                "activity_reduced_repeated",
                "watch",
                "activity_reduced_three_checks",
                f"{house_name}: reduced bird activity has been reported for {CONSECUTIVE_WINDOW} checks in a row.",
                _evidence(window, "activity"),
            )
        )

    return insights
