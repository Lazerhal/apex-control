from pydantic_settings import BaseSettings
from functools import lru_cache

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
    environment: str = "development"
    debug: bool = True

    class Config:
        env_file = ".env"
        case_sensitive = False

@lru_cache()
def get_settings() -> Settings:
    return Settings()
