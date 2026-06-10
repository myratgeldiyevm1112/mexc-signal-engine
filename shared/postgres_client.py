import asyncpg
from shared.config import settings


async def get_postgres_pool() -> asyncpg.Pool:
    """Creates a pool of connections to PostgreSQL."""
    dsn = (
        f"postgresql://{settings.postgres_user}"
        f":{settings.postgres_password}"
        f"@{settings.postgres_host}"
        f":{settings.postgres_port}"
        f"/{settings.postgres_db}"
    )
    return await asyncpg.create_pool(dsn=dsn, min_size=2, max_size=10)