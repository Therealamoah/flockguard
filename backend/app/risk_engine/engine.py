"""Deterministic Risk Engine.

Computes a transparent 0-100 risk score from a Flock Check and the house's
recent historical baseline. This score is never invented by an AI model -
Grok only explains a score the engine already produced.
"""

from app.risk_engine.models import (
    ActivityLevel,
    FeedingBehaviour,
    FlockCheckInput,
    HouseBaseline,
    RiskFactor,
    RiskResult,
    WaterLevel,
)
from app.risk_engine.status import classify_status

MORTALITY_WEIGHT = 35
FEED_WEIGHT = 20
WATER_WEIGHT = 15
ACTIVITY_WEIGHT = 15
OBSERVATION_WEIGHT = 15

# Used only when a house has no check history yet, so a severe first-ever
# reading can still be flagged instead of always scoring as "no baseline
# to compare against". ~0.5%/day is a commonly used concern threshold for
# daily poultry mortality; severity then ramps up to full weight by 2.5%.
REFERENCE_MORTALITY_RATE = 0.005


def _mortality_points(check: FlockCheckInput, baseline: HouseBaseline) -> RiskFactor | None:
    if check.bird_count <= 0:
        return None

    mortality_rate = check.mortality / check.bird_count
    baseline_rate = (
        baseline.avg_daily_mortality / baseline.avg_bird_count
        if baseline.avg_bird_count
        else 0.0
    )

    if baseline_rate > 0:
        ratio = mortality_rate / baseline_rate
        if ratio <= 1:
            return None
        # Scales from 1x baseline (0 pts) to 4x+ baseline (full weight).
        severity = min((ratio - 1) / 3, 1.0)
        label = "Mortality above recent baseline"
    else:
        if mortality_rate <= REFERENCE_MORTALITY_RATE:
            return None
        # Scales from the reference rate (0 pts) to 5x it (full weight).
        severity = min((mortality_rate - REFERENCE_MORTALITY_RATE) / (REFERENCE_MORTALITY_RATE * 4), 1.0)
        label = "Mortality above normal range"

    points = round(severity * MORTALITY_WEIGHT, 1)
    return RiskFactor(key="mortality", label=label, points=points)


def _feed_points(check: FlockCheckInput, baseline: HouseBaseline) -> RiskFactor | None:
    if check.feed_kg is None or not baseline.avg_feed_kg:
        return None

    drop = (baseline.avg_feed_kg - check.feed_kg) / baseline.avg_feed_kg
    if drop <= 0.05:
        return None

    severity = min(drop / 0.5, 1.0)  # 50%+ drop = full weight
    points = round(severity * FEED_WEIGHT, 1)
    return RiskFactor(key="feed", label="Feed consumption dropped", points=points)


def _water_points(check: FlockCheckInput) -> RiskFactor | None:
    if check.water_level == WaterLevel.LOWER:
        return RiskFactor(key="water", label="Water consumption lower than usual", points=WATER_WEIGHT)
    return None


def _activity_points(check: FlockCheckInput) -> RiskFactor | None:
    if check.activity == ActivityLevel.LETHARGIC:
        return RiskFactor(key="activity", label="Birds lethargic", points=ACTIVITY_WEIGHT)
    if check.activity == ActivityLevel.REDUCED:
        return RiskFactor(key="activity", label="Reduced bird activity", points=ACTIVITY_WEIGHT * 0.6)
    return None


def _observation_points(check: FlockCheckInput) -> list[RiskFactor]:
    factors = []
    if check.feeding_behaviour == FeedingBehaviour.NONE:
        factors.append(RiskFactor(key="feeding_behaviour", label="Birds not feeding", points=OBSERVATION_WEIGHT))
    elif check.feeding_behaviour == FeedingBehaviour.REDUCED:
        factors.append(
            RiskFactor(key="feeding_behaviour", label="Reduced feeding behaviour", points=OBSERVATION_WEIGHT * 0.5)
        )

    if check.crowding_observed:
        factors.append(RiskFactor(key="crowding", label="Crowding observed", points=OBSERVATION_WEIGHT * 0.5))

    if check.unusual_sound_observed:
        factors.append(RiskFactor(key="sound", label="Unusual sounds reported", points=OBSERVATION_WEIGHT * 0.5))

    if check.sick_or_injured > 0:
        factors.append(
            RiskFactor(key="sick_or_injured", label="Sick or injured birds observed", points=OBSERVATION_WEIGHT * 0.5)
        )

    return factors


def compute_risk(check: FlockCheckInput, baseline: HouseBaseline) -> RiskResult:
    factors: list[RiskFactor] = []

    for factor in (
        _mortality_points(check, baseline),
        _feed_points(check, baseline),
        _water_points(check),
        _activity_points(check),
    ):
        if factor:
            factors.append(factor)

    factors.extend(_observation_points(check))

    raw_score = sum(f.points for f in factors)
    score = round(min(raw_score, 100))

    return RiskResult(score=score, status=classify_status(score), factors=factors)
