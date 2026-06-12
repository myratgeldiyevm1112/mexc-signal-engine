import redis.asyncio as aioredis
from shared.config import settings

def get_redis_client() -> aioredis.Redis:
    """Creates and returns an asynchronous Redis client with connection pool."""
    pool = aioredis.ConnectionPool(
        host=settings.redis_host,
        port=settings.redis_port,
        db=settings.redis_db,
        password=settings.redis_password or None,
        decode_responses=True,
        max_connections=200,
    )
    return aioredis.Redis(connection_pool=pool)