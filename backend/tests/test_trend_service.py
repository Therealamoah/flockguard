from app.services.trend_service import detect_trends


def _checks(*mortalities):
    # newest-first, matching how flock_checks_ref queries are ordered
    return [{"id": f"c{i}", "recorded_at": f"2026-01-0{5 - i}T06:00:00+00:00", "mortality": m} for i, m in enumerate(mortalities)]


def test_mortality_increase_detected_across_three_checks():
    # newest-first: 6 (today) > 4 (yesterday) > 2 (day before) => rising trend
    checks = _checks(6, 4, 2)
    insights = detect_trends("h1", "House A", checks)
    types = [i["type"] for i in insights]
    assert "mortality_increase" in types


def test_no_trend_when_values_flat():
    checks = _checks(2, 2, 2)
    insights = detect_trends("h1", "House A", checks)
    assert insights == []


def test_no_trend_with_fewer_than_three_checks():
    checks = _checks(6, 2)
    insights = detect_trends("h1", "House A", checks)
    assert insights == []


def test_feed_decline_detected():
    checks = [
        {"id": "c0", "recorded_at": "2026-01-05T06:00:00+00:00", "feed_kg": 20},
        {"id": "c1", "recorded_at": "2026-01-04T06:00:00+00:00", "feed_kg": 25},
        {"id": "c2", "recorded_at": "2026-01-03T06:00:00+00:00", "feed_kg": 30},
    ]
    insights = detect_trends("h1", "House A", checks)
    assert any(i["type"] == "feed_decline" for i in insights)


def test_water_low_repeated_detected():
    checks = [{"id": f"c{i}", "recorded_at": "2026-01-0{}T06:00:00+00:00".format(5 - i), "water_level": "lower"} for i in range(3)]
    insights = detect_trends("h1", "House A", checks)
    assert any(i["type"] == "water_low_repeated" for i in insights)


def test_insight_carries_evidence_with_check_ids():
    checks = _checks(6, 4, 2)
    insights = detect_trends("h1", "House A", checks)
    mortality_insight = next(i for i in insights if i["type"] == "mortality_increase")
    assert len(mortality_insight["evidence"]) == 3
    assert {e["check_id"] for e in mortality_insight["evidence"]} == {"c0", "c1", "c2"}
