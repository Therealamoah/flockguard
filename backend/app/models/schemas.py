import re
from datetime import date, datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, field_validator

from app.core.roles import Role
from app.risk_engine.models import (
    ActivityLevel,
    FeedingBehaviour,
    RiskFactor,
    WaterLevel,
)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


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
    transcript: str | None = None


# ---------------------------------------------------------------------------
# Team / membership
# ---------------------------------------------------------------------------


class InviteMemberRequest(BaseModel):
    email: str
    role: Role

    @field_validator("email")
    @classmethod
    def _validate_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not _EMAIL_RE.match(value):
            raise ValueError("Enter a valid email address")
        return value

    @field_validator("role")
    @classmethod
    def _no_owner_invites(cls, value: Role) -> Role:
        # Ownership isn't handed out via invitation - it's the org creator,
        # or transferred deliberately (not implemented - not needed for pilot).
        if value == Role.OWNER:
            raise ValueError("Cannot invite someone directly as owner")
        return value


class ForgotPasswordRequest(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def _validate_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not _EMAIL_RE.match(value):
            raise ValueError("Enter a valid email address")
        return value


class UpdateMemberRoleRequest(BaseModel):
    """Role can be set to OWNER here (an existing owner adding a co-owner) -
    self-promotion isn't a concern since only an owner can call this route
    at all (app/core/permissions.py::require_owner). Demoting the org's
    last remaining owner is blocked in the route handler, where the actual
    owner count is known."""

    role: Role


class AcceptInvitationRequest(BaseModel):
    org_id: str
    invitation_id: str


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


class NotificationChannels(BaseModel):
    in_app: bool = True
    # Only ever true once a push/email provider is actually wired up -
    # never surface a channel as usable before it's real.
    push: bool = False
    email: bool = False
    whatsapp: Literal["coming_soon"] = "coming_soon"
    sms: Literal["coming_soon"] = "coming_soon"


class NotificationPreferences(BaseModel):
    critical_alerts: bool = True
    warning_alerts: bool = True
    watch_alerts: bool = False
    morning_check_reminder: bool = True
    evening_check_reminder: bool = True
    daily_farm_brief: bool = True
    channels: NotificationChannels = NotificationChannels()


class AIPreferences(BaseModel):
    ai_explanations_enabled: bool = True
    daily_ai_brief_enabled: bool = True
    proactive_insights_enabled: bool = True


class FarmSettingsUpdate(BaseModel):
    """PATCH semantics - every field optional, only supplied ones change."""

    name: str | None = None
    country: str | None = None
    timezone: str | None = None
    temperature_unit: Literal["celsius", "fahrenheit"] | None = None
    weight_unit: Literal["kg", "lb"] | None = None
    contact_number: str | None = None

    morning_check_enabled: bool | None = None
    morning_check_start: str | None = None
    morning_check_end: str | None = None
    evening_check_enabled: bool | None = None
    evening_check_start: str | None = None
    evening_check_end: str | None = None

    notification_preferences: NotificationPreferences | None = None
    ai_preferences: AIPreferences | None = None

    @field_validator("timezone")
    @classmethod
    def _validate_timezone(cls, value: str | None) -> str | None:
        if value is None:
            return value
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"Unrecognized IANA timezone: {value}") from exc
        return value


class AccountUpdate(BaseModel):
    display_name: str


class DeleteFarmRequest(BaseModel):
    confirmation: str


# ---------------------------------------------------------------------------
# Billing
# ---------------------------------------------------------------------------


class SubscriptionPlan(str, Enum):
    PILOT = "pilot"
    STARTER = "starter"
    GROWTH = "growth"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class CheckoutRequest(BaseModel):
    """Enterprise is deliberately not a valid value - it's contact-sales
    only, never a self-serve Paystack checkout (see BillingPage.jsx)."""

    plan: SubscriptionPlan

    @field_validator("plan")
    @classmethod
    def _must_be_self_serve(cls, value: SubscriptionPlan) -> SubscriptionPlan:
        if value not in (SubscriptionPlan.STARTER, SubscriptionPlan.GROWTH, SubscriptionPlan.PRO):
            raise ValueError("plan must be one of: starter, growth, pro")
        return value


class VerifyPaymentRequest(BaseModel):
    reference: str
