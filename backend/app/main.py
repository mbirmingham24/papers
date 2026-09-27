import asyncio
import logging
from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_session
from app.core.redis import get_redis

logger = logging.getLogger(__name__)

settings = get_settings()

app = FastAPI(
    title="arXiv semantic search",
    # Interactive docs are handy locally; no reason to expose them in prod.
    docs_url=None if settings.environment == "prod" else "/docs",
    redoc_url=None,
)


@app.get("/livez")
async def livez() -> dict[str, str]:
    """Liveness for the host's prober: the process is up. Touches no dependencies, so frequent
    probes cost nothing and don't keep Neon awake. /health is the dependency check."""
    return {"status": "ok"}


# Long enough for Neon to wake from scale-to-zero, short enough not to hang the caller.
HEALTH_DB_TIMEOUT_S = 5
# Redis doesn't scale to zero, so a slow PING means something is actually wrong.
HEALTH_REDIS_TIMEOUT_S = 2

# Failure details go to the logs only: /health is public. One line, not a traceback,
# so a dependency outage doesn't flood the logs.


async def _database_ok(session: AsyncSession) -> bool:
    try:
        async with asyncio.timeout(HEALTH_DB_TIMEOUT_S):
            await session.execute(text("SELECT 1"))
    except (SQLAlchemyError, OSError, TimeoutError) as exc:
        logger.warning("health: database check failed: %r", exc)
        return False
    return True


async def _redis_ok(redis: Redis) -> bool:
    try:
        async with asyncio.timeout(HEALTH_REDIS_TIMEOUT_S):
            await redis.ping()
    except (RedisError, OSError, TimeoutError) as exc:
        logger.warning("health: redis check failed: %r", exc)
        return False
    return True


@app.get("/health")
async def health(
    session: Annotated[AsyncSession, Depends(get_session)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> JSONResponse:
    # Concurrent, so the response takes as long as the slower check, not the sum of both.
    database_ok, redis_ok = await asyncio.gather(_database_ok(session), _redis_ok(redis))
    body = {
        "status": "ok" if database_ok and redis_ok else "error",
        "database": "ok" if database_ok else "unreachable",
        "redis": "ok" if redis_ok else "unreachable",
    }
    return JSONResponse(body, status_code=200 if database_ok and redis_ok else 503)
