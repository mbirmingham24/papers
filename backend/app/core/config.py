from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: Literal["local", "test", "prod"] = "local"
    # Default matches docker-compose's Postgres as seen from the host. Prod sets its own.
    database_url: str = "postgresql+asyncpg://papers:papers@localhost:5432/papers"


@lru_cache
def get_settings() -> Settings:
    return Settings()
