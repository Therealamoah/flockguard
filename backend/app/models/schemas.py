from datetime import date, datetime
from enum import Enum
from typing import Any

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
    # Added for risk-history/trend display ("58 -> 81, +23") without a
    # second Firestore scan. None on a house's first-ever check.
    previous_risk_score: int | None = None
    risk_change: int | None = None
    # Structured Morning-vs-Evening diff (see app/services/comparison_service.py).
    # Present only on evening/emergency checks that had a same-day Morning
    # Check to compare against; None otherwise (never an error).
    morning_comparison: dict[str, Any] | None = None


class AskRequest(BaseModel):
    question: str
    house_id: str | None = None
    farm_id: str | None = None


class ExplainCheckRequest(BaseModel):
    farm_id: str
    house_id: str
    check_id: str


class FindingCategory(str, Enum):
    EVERYTHING_NORMAL = "everything_normal"
    WATER_ISSUE = "water_issue"
    FEED_ISSUE = "feed_issue"
    VENTILATION_ISSUE = "ventilation_issue"
    SICK_BIRDS_OBSERVED = "sick_birds_observed"
    BEHAVIOUR_ISSUE = "behaviour_issue"
    OTHER = "other"


class FlockCreate(BaseModel):
    bird_type: BirdType = BirdType.BROILER
    breed: str
    start_date: date
    initial_bird_count: int


class FlockUpdate(BaseModel):
    status: FlockStatus


class InspectionCreate(BaseModel):
    findings: str
    # New, all optional so existing callers/older clients keep working
    # unchanged - see CHECKLIST/audit Phase 7.
    finding_category: FindingCategory | None = None
    action_taken: str | None = None
    started_at: datetime | None = None
    alert_id: str | None = None
    photo_url: str | None = None
    photo_public_id: str | None = None


class MediaUploadResponse(BaseModel):
    url: str
    public_id: str
