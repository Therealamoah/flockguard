import json
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173"]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors_origins(cls, value):
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    firebase_project_id: str = ""
    firebase_service_account_json: str = ""

    cloudinary_cloud_name: str = ""
    cloudinary_api_key: str = ""
    cloudinary_api_secret: str = ""

    # AI provider config, OpenAI-chat-completions-compatible. Currently
    # pointed at OpenRouter (proxies to x-ai/grok-*) until the school issues
    # a direct xAI key - switching later is an env change only:
    #   direct Grok:  GROK_API_BASE_URL=https://api.x.ai/v1           GROK_MODEL=grok-4.3
    #   OpenRouter:   GROK_API_BASE_URL=https://openrouter.ai/api/v1  GROK_MODEL=x-ai/grok-4.3
    grok_api_key: str = ""
    grok_api_base_url: str = "https://openrouter.ai/api/v1"
    grok_model: str = "x-ai/grok-4.3"
    # OpenRouter's free-credit balance can't cover this model's 65536-token
    # default; keep responses capped until the school's paid key is in.
    grok_max_tokens: int = 800

    # Sent as OpenRouter's optional attribution headers; harmless elsewhere.
    app_public_url: str = "http://localhost:5173"
    app_name: str = "FlockGuard AI"

    # Voice-note transcription for the Flock Check "Record Voice Note"
    # button - Groq-specific (api.groq.com/openai/v1/audio/transcriptions),
    # not part of the OpenAI-chat-completions surface the other providers
    # above share, so grok_service.transcribe() no-ops when grok_api_base_url
    # isn't Groq's.
    grok_transcribe_model: str = "whisper-large-v3-turbo"

    # Rate limits, as slowapi/limits strings (e.g. "20/minute"). Kept
    # generous enough not to get in a real farmer's way during normal use
    # (a handful of Flock Checks a day, occasional AI questions) while
    # bounding the cost/abuse surface of the AI and upload endpoints.
    rate_limit_ask: str = "15/minute"
    rate_limit_media_upload: str = "30/minute"
    rate_limit_flock_check: str = "30/minute"

    # Upload limits enforced server-side in app/services/media_validation.py
    # - never trust the frontend or the file extension alone.
    max_image_upload_mb: float = 8.0
    max_audio_upload_mb: float = 20.0

    # Team invite emails (app/services/email_service.py) - SMTP, e.g. Gmail
    # with an App Password (myaccount.google.com/apppasswords; needs 2FA
    # enabled on the account - a regular password will not work here).
    # Left blank, invite emails are silently skipped (create_invitation still
    # succeeds; the frontend falls back to "share this invite directly").
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""  # defaults to smtp_username if blank
    smtp_from_name: str = "FlockGuard"

    # Paystack (real payment processing for Starter/Growth/Pro - see
    # app/services/paystack_service.py and app/services/billing_service.py's
    # PLAN_CATALOG). Left blank, /billing/checkout fails clearly rather than
    # pretending to charge anyone - PILOT stays free and fully usable either
    # way. The three PAYSTACK_PLAN_CODE_* vars are Paystack "Plan" codes
    # (plm_...), one per paid tier, created once via the Paystack dashboard
    # (Plans -> Create Plan, GHS, monthly interval, amount matching
    # PLAN_CATALOG) or via `POST https://api.paystack.co/plan` - Paystack
    # ties a customer's recurring billing to the Plan, not to a raw amount,
    # so these must exist before checkout works.
    paystack_secret_key: str = ""
    paystack_public_key: str = ""
    paystack_plan_code_starter: str = ""
    paystack_plan_code_growth: str = ""
    paystack_plan_code_pro: str = ""

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"


settings = Settings()
