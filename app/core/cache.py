from redis.asyncio import Redis
from app.core.config import settings

_redis: Redis | None = None

async def get_redis() -> Redis:
    global _redis
    if _redis is None:
        _redis = Redis.from_url(settings.redis_url, decode_responses=True)
    return _redis

async def check_redis_connection() -> bool:
    try:
        r = await get_redis()
        return bool(await r.ping())
    except Exception:
        return False
