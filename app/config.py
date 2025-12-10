# app/config.py
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # 🔧 Autoriser des variables en plus dans le .env
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"   # <<< clé de la solution
    )

    openai_api_key: str
    openai_model: str = "gpt-4o-mini"

    telegram_api_id: int
    telegram_api_hash: str
    telegram_session: str = "telegram_session"

    sources_telegram: str = ""

    max_messages_per_channel: int = 50
    batch_size: int = 20


@lru_cache
def get_settings() -> Settings:
    return Settings()
