# app/config.py
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict



import os
from typing import ClassVar



class Settings(BaseSettings):
    # 🔧 Autoriser des variables en plus dans le .env
    # Utilise .env si présent, sinon .env.example
    env_file: ClassVar[str] = ".env" if os.path.exists(os.path.join(os.path.dirname(__file__), "..", ".env")) else ".env.example"
    model_config = SettingsConfigDict(
        env_file=env_file,
        env_file_encoding="utf-8",
        extra="ignore"   # <<< clé de la solution
    )

    openai_api_key: str
    openai_model: str = "gpt-4o-mini"

    telegram_api_id: int
    telegram_api_hash: str
    telegram_session: str | None = None  # Optionnel maintenant

    sources_telegram: str = ""

    max_messages_per_channel: int = 50
    batch_size: int = 20


@lru_cache
def get_settings() -> Settings:
    return Settings()
