from typing import Iterable

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


async def cleanup_cache_keys(patterns: Iterable[str], *, batch_size: int = 100) -> int:
    """Remove chaves de cache que correspondam aos padrões informados."""
    redis = await get_redis()
    removed = 0
    for pattern in patterns:
        async for key in redis.scan_iter(match=pattern, count=batch_size):
            try:
                removed += await redis.delete(key)
            except Exception:
                # ignora falha isolada e continua
                continue
    return removed
