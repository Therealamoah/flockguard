from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel

from app.risk_engine.models import (
    ActivityLevel,
    FeedingBehaviour,
    RiskFactor,
    WaterLevel,
)


class CheckPeriod(str, Enum):
    MORNING = "morning"
    EVENING = "evening"
    EMERGENCY = "emergency"


class FlockStatus(str, Enum):
    ACTIVE = "active"
    CLOSED = "closed"


class BirdType(str, Enum):
    BROILER = "broiler"
    LAYER = "layer"
    BREEDER = "breeder"


class FarmCreate(BaseModel):
    name: str


class HouseCreate(BaseModel):
    name: str
    bird_capacity: int | None = None


class FlockCheckCreate(BaseModel):
    period: CheckPeriod
    bird_count: int
    mortality: int = 0
    sick_or_injured: int = 0
    feed_kg: float | None = None
    water_level: WaterLevel = WaterLevel.NORMAL
    # Optional precise reading alongside the always-required qualitative
    # level above - never forces a farmer without a meter to guess a number.
    water_liters: float | None = None
    activity: ActivityLevel = ActivityLevel.NORMAL
    feeding_behaviour: FeedingBehaviour = FeedingBehaviour.NORMAL
    crowding_observed: bool = False
    unusual_sound_observed: bool = False
    # Only entered when the farmer already has reliable equipment - never
    # required, and not yet fed into the Risk Engine's scoring.
    temperature_c: float | None = None
    humidity_pct: float | None = None
    notes: str | None = None
    photo_url: str | None = None
    photo_public_id: str | None = None
    audio_url: str | None = None
    audio_public_id: str | None = None


class FlockCheckResponse(BaseModel):
    id: str
    house_id: str
    period: CheckPeriod
    recorded_at: datetime
    risk_score: int
    risk_status: str
    risk_factors: list[RiskFactor]
    notes: str | None = None


class AskRequest(BaseModel):
    question: str
    house_id: str | None = None


class FlockCreate(BaseModel):
    bird_type: BirdType = BirdType.BROILER
    breed: str
    start_date: date
    initial_bird_count: int


class FlockUpdate(BaseModel):
    status: FlockStatus


class InspectionCreate(BaseModel):
    findings: str
    alert_id: str | None = None
    photo_url: str | None = None
    photo_public_id: str | None = None


class MediaUploadResponse(BaseModel):
    url: str
    public_id: str
