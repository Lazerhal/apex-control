from pydantic import Field, field_validator
from pydantic_settings import BaseSettings
from functools import lru_cache

MIN_SECRET_LENGTH = 32

class Settings(BaseSettings):
    database_url: str
    apex_session_secret: str
    telegram_bot_token: str = ""
    telegram_owner_chat_id: str = ""
    hermes_telegram_bot_token: str = ""
    cloudflare_tunnel_token: str = ""
    anthropic_api_key: str = ""
    google_api_key: str = ""
    deepseek_api_key: str = ""
    openai_api_key: str = ""
    github_token: str = ""
    github_username: str = "Lazerhal"
    apex_dashboard_username: str = "hunter"
    apex_dashboard_password_hash: str = ""
    jwt_secret_key: str = Field("", validate_default=True)
    # Shared by the API and the Telegram bot (X-Bot-Auth). Empty turns bot auth off.
    apex_internal_key: str = ""
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 24
    environment: str = "development"
    debug: bool = True

    @field_validator("jwt_secret_key")
    @classmethod
    def jwt_secret_key_is_long_enough(cls, value: str) -> str:
        if len(value.strip()) < MIN_SECRET_LENGTH:
            raise ValueError(f"JWT_SECRET_KEY must be set to at least {MIN_SECRET_LENGTH} characters")
        return value

    @field_validator("apex_internal_key")
    @classmethod
    def internal_key_is_long_enough(cls, value: str) -> str:
        if not value.isascii():  # it is sent as an HTTP header
            raise ValueError("APEX_INTERNAL_KEY must contain only ASCII characters")
        if value and len(value.strip()) < MIN_SECRET_LENGTH:
            raise ValueError(f"APEX_INTERNAL_KEY must be at least {MIN_SECRET_LENGTH} characters")
        return value

    class Config:
        env_file = ".env"
        case_sensitive = False
        hide_input_in_errors = True  # startup errors must not print secrets

@lru_cache()
def get_settings() -> Settings:
    return Settings()
