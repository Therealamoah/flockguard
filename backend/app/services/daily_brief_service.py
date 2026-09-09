"""Deterministic daily farm summary.

Always computed in plain Python from real farm/house/alert data - this is
what actually powers the Daily Brief. An AI-reworded version of
`brief_text` may be layered on top at the route level (see
app/api/routes/ask.py::daily_brief), but this function's output is never
itself AI-generated, so the feature keeps working verbatim if Grok is
unavailable.
"""

from __future__ import annotations

from datetime import datetime, timezone


def build_daily_brief(farm_status: dict) -> dict:
    houses_total = farm_status["houses_total"]
    stable = farm_status["houses_stable"]
    needs_attention = farm_status["houses_needing_attention"]
    missing_morning = farm_status["houses_missing_morning_check"]
    critical_alerts = [a for a in farm_status["active_alerts"] if a.get("status") == "critical"]

    lines: list[str] = []
    if houses_total == 0:
        lines.append("No houses set up yet - add a house to start getting daily briefs.")
    else:
        lines.append(f"{stable} of {houses_total} house{'s' if houses_total != 1 else ''} stable today.")

        if needs_attention:
            worst = needs_attention[0]
            lines.append(
                f"{worst['house_name']} needs the most attention right now "
                f"(risk {worst['risk_score']}, {worst['risk_status']})."
            )

        if missing_morning:
            lines.append(f"Morning Check not yet completed for: {', '.join(missing_morning)}.")

        lines.append(
            f"{len(critical_alerts)} critical alert(s) active."
            if critical_alerts
            else "No critical alerts are active."
        )

        if farm_status.get("trend_insights"):
            lines.append(farm_status["trend_insights"][0]["message"])

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "houses_total": houses_total,
        "houses_stable": stable,
        "houses_needing_attention": needs_attention,
        "houses_missing_morning_check": missing_morning,
        "critical_alert_count": len(critical_alerts),
        "trend_insights": farm_status.get("trend_insights", []),
        "brief_text": " ".join(lines),
    }
