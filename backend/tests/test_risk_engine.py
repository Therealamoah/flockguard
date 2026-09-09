from app.risk_engine.engine import compute_risk
from app.risk_engine.models import (
    ActivityLevel,
    FeedingBehaviour,
    FlockCheckInput,
    HouseBaseline,
    WaterLevel,
)
from app.risk_engine.status import classify_status


def test_classify_status_boundaries():
    assert classify_status(0) == "normal"
    assert classify_status(24) == "normal"
    assert classify_status(25) == "watch"
    assert classify_status(49) == "watch"
    assert classify_status(50) == "warning"
    assert classify_status(74) == "warning"
    assert classify_status(75) == "critical"
    assert classify_status(100) == "critical"


def test_normal_score_no_baseline_all_normal_readings():
    check = FlockCheckInput(bird_count=1000, mortality=1)
    result = compute_risk(check, HouseBaseline())
    assert result.score == 0
    assert result.status == "normal"
    assert result.factors == []


def test_watch_score_from_behaviour_signals():
    check = FlockCheckInput(
        bird_count=1000,
        mortality=0,
        activity=ActivityLevel.REDUCED,
        feeding_behaviour=FeedingBehaviour.REDUCED,
        crowding_observed=True,
        water_level=WaterLevel.LOWER,
    )
    result = compute_risk(check, HouseBaseline())
    assert 25 <= result.score <= 49
    assert result.status == "watch"


def test_warning_score():
    check = FlockCheckInput(
        bird_count=1000,
        mortality=0,
        activity=ActivityLevel.LETHARGIC,
        feeding_behaviour=FeedingBehaviour.NONE,
        water_level=WaterLevel.LOWER,
        crowding_observed=True,
    )
    result = compute_risk(check, HouseBaseline())
    assert 50 <= result.score <= 74
    assert result.status == "warning"


def test_critical_score_from_mortality_spike_above_baseline():
    baseline = HouseBaseline(avg_daily_mortality=2, avg_bird_count=1000)
    check = FlockCheckInput(
        bird_count=1000,
        mortality=20,  # 10x the baseline daily mortality rate
        activity=ActivityLevel.LETHARGIC,
        feeding_behaviour=FeedingBehaviour.NONE,
        water_level=WaterLevel.LOWER,
    )
    result = compute_risk(check, baseline)
    assert result.score >= 75
    assert result.status == "critical"
    assert any(f.key == "mortality" for f in result.factors)


def test_missing_optional_feed_value_does_not_crash_or_score():
    baseline = HouseBaseline(avg_feed_kg=30.0)
    check = FlockCheckInput(bird_count=1000, mortality=0, feed_kg=None)
    result = compute_risk(check, baseline)
    assert result.score == 0
    assert not any(f.key == "feed" for f in result.factors)


def test_zero_bird_count_does_not_crash():
    check = FlockCheckInput(bird_count=0, mortality=0)
    result = compute_risk(check, HouseBaseline())
    assert result.score == 0
    assert result.status == "normal"


def test_no_history_first_check_uses_absolute_reference_rate():
    # No baseline at all (house's first-ever check) - severe mortality should
    # still be flagged via the absolute reference rate, not silently pass
    # because there's nothing to compare against yet.
    check = FlockCheckInput(bird_count=1000, mortality=30)  # 3% daily mortality
    result = compute_risk(check, HouseBaseline())
    assert result.score > 0
    assert any(f.key == "mortality" for f in result.factors)
