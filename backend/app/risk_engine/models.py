from enum import Enum

from pydantic import BaseModel, Field


class ActivityLevel(str, Enum):
    NORMAL = "normal"
    REDUCED = "reduced"
    LETHARGIC = "lethargic"


class FeedingBehaviour(str, Enum):
    NORMAL = "normal"
    REDUCED = "reduced"
    NONE = "none"


class WaterLevel(str, Enum):
    NORMAL = "normal"
    LOWER = "lower"
    HIGHER = "higher"


class FlockCheckInput(BaseModel):
    """The subset of a Flock Check relevant to risk scoring."""

    bird_count: int
    mortality: int = 0
    sick_or_injured: int = 0
    feed_kg: float | None = None
    water_level: WaterLevel = WaterLevel.NORMAL
    activity: ActivityLevel = ActivityLevel.NORMAL
    feeding_behaviour: FeedingBehaviour = FeedingBehaviour.NORMAL
    crowding_observed: bool = False
    unusual_sound_observed: bool = False


class HouseBaseline(BaseModel):
    """Recent historical averages for the same house, used for comparison."""

    avg_daily_mortality: float = 0.0
    avg_feed_kg: float | None = None
    avg_bird_count: int | None = None


class RiskFactor(BaseModel):
    key: str
    label: str
    points: float


class RiskResult(BaseModel):
    score: int = Field(ge=0, le=100)
    status: str
    factors: list[RiskFactor]
