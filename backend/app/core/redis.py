from redis.asyncio import Redis

from app.core.config import get_settings

# One client (and connection pool) per process, like the DB engine. Creating it doesn't connect;
# the first command does. A rediss:// URL (Upstash) turns on TLS; redis:// is plain TCP.
redis_client = Redis.from_url(get_settings().redis_url)


async def get_redis() -> Redis:
    """FastAPI dependency, so tests can swap in a different client."""
    return redis_client
