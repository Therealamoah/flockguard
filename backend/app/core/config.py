from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    cors_origins: list[str] = ["http://localhost:5173"]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors_origins(cls, value):
        if isinstance(value, str) and not value.strip().startswith("["):
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


settings = Settings()
