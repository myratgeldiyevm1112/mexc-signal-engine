import redis.asyncio as aioredis

from shared.config import settings
from shared.constants import COOLDOWN_KEY


async def is_on_cooldown(redis: aioredis.Redis, symbol: str) -> bool:
    """Check if symbol is on cooldown after a signal."""
    key = COOLDOWN_KEY.format(symbol=symbol)
    return await redis.exists(key) == 1


async def set_cooldown(redis: aioredis.Redis, symbol: str) -> None:
    """Set cooldown for symbol. Expires automatically via TTL."""
    key = COOLDOWN_KEY.format(symbol=symbol)
    ttl = settings.signal_cooldown_minutes * 60
    await redis.set(key, "1", ex=ttl)