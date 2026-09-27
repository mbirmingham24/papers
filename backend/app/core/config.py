from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: Literal["local", "test", "prod"] = "local"
    # No default: a missing or misspelled DATABASE_URL must fail at startup,
    # not silently point prod at localhost. Local dev gets it from .env.
    database_url: str
    # Same rule. redis:// locally, rediss:// (TLS) for Upstash in prod.
    redis_url: str


@lru_cache
def get_settings() -> Settings:
    return Settings()
