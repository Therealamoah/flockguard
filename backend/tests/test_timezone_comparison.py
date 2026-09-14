"""Farm-timezone-aware Morning/Evening pairing.

These scenarios specifically target cases where a naive UTC-calendar-date
comparison gives the WRONG answer and the farm's own IANA timezone gives
the right one - not just "does it still work in UTC."
"""

from app.services.comparison_service import build_morning_evening_comparison


def _check(id_, period, recorded_at_utc_iso, **kwargs):
    return {
        "id": id_,
        "period": period,
        "recorded_at": recorded_at_utc_iso,
        "mortality": 0,
        "feed_kg": None,
        "water_level": "normal",
        "activity": "normal",
        "feeding_behaviour": "normal",
        "risk_score": 0,
        **kwargs,
    }


def test_africa_accra_same_local_day_pairs():
    # Accra is UTC+0 with no DST - local time equals the UTC timestamp here.
    morning = _check("m1", "morning", "2026-01-05T07:00:00+00:00", mortality=1)
    evening = _check("e1", "evening", "2026-01-05T18:00:00+00:00", mortality=3)

    comparison = build_morning_evening_comparison([morning], evening, farm_timezone="Africa/Accra")

    assert comparison is not None
    assert comparison["mortality_change"] == 2


def test_timezone_ahead_of_utc_pairs_checks_that_span_a_utc_date_boundary():
    """Africa/Nairobi is UTC+3. These two checks fall on DIFFERENT UTC
    calendar dates (Jan 5 vs Jan 6) but the SAME Nairobi local date (both
    Jan 6) - the old UTC-only comparison would have missed this pairing
    entirely."""
    morning = _check("m1", "morning", "2026-01-05T22:00:00+00:00", mortality=2)  # 2026-01-06 01:00 Nairobi
    evening = _check("e1", "evening", "2026-01-06T02:00:00+00:00", mortality=5)  # 2026-01-06 05:00 Nairobi

    # Sanity: genuinely different UTC calendar dates.
    assert morning["recorded_at"][:10] != evening["recorded_at"][:10]

    comparison = build_morning_evening_comparison([morning], evening, farm_timezone="Africa/Nairobi")

    assert comparison is not None
    assert comparison["mortality_change"] == 3

    # And confirm the UTC-fallback (no farm timezone) genuinely fails to
    # pair these same two checks - proving the fix is load-bearing, not
    # cosmetic.
    assert build_morning_evening_comparison([morning], evening, farm_timezone=None) is None


def test_timezone_behind_utc_pairs_checks_that_span_a_utc_date_boundary():
    """America/New_York is UTC-5 in January (standard time, no DST
    ambiguity). Same shape as the Nairobi case, opposite direction."""
    morning = _check("m1", "morning", "2026-01-05T10:00:00+00:00", mortality=1)  # 2026-01-05 05:00 EST
    evening = _check("e1", "evening", "2026-01-06T02:00:00+00:00", mortality=4)  # 2026-01-05 21:00 EST

    assert morning["recorded_at"][:10] != evening["recorded_at"][:10]

    comparison = build_morning_evening_comparison([morning], evening, farm_timezone="America/New_York")

    assert comparison is not None
    assert comparison["mortality_change"] == 3
    assert build_morning_evening_comparison([morning], evening, farm_timezone=None) is None


def test_checks_around_local_midnight_on_different_days_do_not_pair():
    """Only 20 minutes apart in wall-clock UTC time, but on opposite sides
    of local midnight in Accra - must NOT be treated as the same farm day."""
    late_night = _check("m1", "morning", "2026-01-05T23:50:00+00:00")  # Accra 23:50, Jan 5
    just_after_midnight = _check("e1", "evening", "2026-01-06T00:10:00+00:00")  # Accra 00:10, Jan 6

    comparison = build_morning_evening_comparison(
        [late_night], just_after_midnight, farm_timezone="Africa/Accra"
    )
    assert comparison is None


def test_farm_without_timezone_falls_back_to_utc_like_before():
    morning = _check("m1", "morning", "2026-01-05T06:00:00+00:00", mortality=1)
    evening = _check("e1", "evening", "2026-01-05T18:00:00+00:00", mortality=4)

    comparison = build_morning_evening_comparison([morning], evening, farm_timezone=None)
    assert comparison is not None
    assert comparison["mortality_change"] == 3


def test_unrecognized_timezone_string_falls_back_to_utc_instead_of_crashing():
    morning = _check("m1", "morning", "2026-01-05T06:00:00+00:00", mortality=1)
    evening = _check("e1", "evening", "2026-01-05T18:00:00+00:00", mortality=4)

    comparison = build_morning_evening_comparison([morning], evening, farm_timezone="Not/ARealZone")
    assert comparison is not None  # degrades to UTC rather than raising
