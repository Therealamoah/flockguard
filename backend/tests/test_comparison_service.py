from app.services.comparison_service import build_morning_evening_comparison, find_check_for_period_on_date


def _check(id_, period, recorded_at, **kwargs):
    return {
        "id": id_,
        "period": period,
        "recorded_at": recorded_at,
        "mortality": 0,
        "feed_kg": None,
        "water_level": "normal",
        "activity": "normal",
        "feeding_behaviour": "normal",
        "risk_score": 0,
        **kwargs,
    }


def test_correct_pairing_same_day():
    morning = _check("m1", "morning", "2026-01-05T06:00:00+00:00", mortality=1, feed_kg=30, risk_score=22)
    evening = _check("e1", "evening", "2026-01-05T18:00:00+00:00", mortality=4, feed_kg=22, risk_score=58, water_level="lower", activity="reduced")

    comparison = build_morning_evening_comparison([morning], evening)

    assert comparison is not None
    assert comparison["morning_check_id"] == "m1"
    assert comparison["evening_check_id"] == "e1"
    assert comparison["mortality_change"] == 3
    assert comparison["feed_change"] == -8
    assert comparison["risk_change"] == 36
    assert comparison["water_changed"] is True
    assert comparison["activity_changed"] is True
    assert "mortality_increased" in comparison["summary_flags"]
    assert "feed_decreased" in comparison["summary_flags"]
    assert "risk_increased" in comparison["summary_flags"]


def test_no_morning_check_returns_none_not_error():
    evening = _check("e1", "evening", "2026-01-05T18:00:00+00:00")
    assert build_morning_evening_comparison([], evening) is None


def test_multiple_morning_checks_same_day_picks_latest():
    early = _check("m1", "morning", "2026-01-05T05:00:00+00:00", mortality=1)
    late = _check("m2", "morning", "2026-01-05T07:30:00+00:00", mortality=2)
    evening = _check("e1", "evening", "2026-01-05T18:00:00+00:00", mortality=5)

    comparison = build_morning_evening_comparison([early, late], evening)

    assert comparison["morning_check_id"] == "m2"
    assert comparison["mortality_change"] == 3  # 5 - 2, not 5 - 1


def test_emergency_check_between_morning_and_evening_does_not_confuse_pairing():
    morning = _check("m1", "morning", "2026-01-05T06:00:00+00:00", mortality=1)
    emergency = _check("x1", "emergency", "2026-01-05T12:00:00+00:00", mortality=3)
    evening = _check("e1", "evening", "2026-01-05T18:00:00+00:00", mortality=6)

    # The emergency check itself compares against the morning check...
    emergency_comparison = build_morning_evening_comparison([morning], emergency)
    assert emergency_comparison["morning_check_id"] == "m1"
    assert emergency_comparison["mortality_change"] == 2

    # ...and the evening check still pairs with the real morning check, not
    # the emergency one, even when both are in its history.
    evening_comparison = build_morning_evening_comparison([morning, emergency], evening)
    assert evening_comparison["morning_check_id"] == "m1"
    assert evening_comparison["mortality_change"] == 5


def test_different_day_morning_check_is_not_used():
    yesterday_morning = _check("m1", "morning", "2026-01-04T06:00:00+00:00")
    evening = _check("e1", "evening", "2026-01-05T18:00:00+00:00")
    assert build_morning_evening_comparison([yesterday_morning], evening) is None


def test_morning_check_itself_has_no_comparison():
    morning = _check("m1", "morning", "2026-01-05T06:00:00+00:00")
    assert build_morning_evening_comparison([], morning) is None


def test_find_check_for_period_on_date_ignores_checks_after_reference_time():
    from datetime import datetime, timezone

    morning = _check("m1", "morning", "2026-01-05T09:00:00+00:00")
    result = find_check_for_period_on_date(
        [morning], "morning", datetime(2026, 1, 5, tzinfo=timezone.utc).date(), before=datetime(2026, 1, 5, 8, 0, tzinfo=timezone.utc)
    )
    assert result is None
