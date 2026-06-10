import asyncpg
import redis.asyncio as aioredis
from loguru import logger

from shared.constants import STREAM_SIGNALS
from services.analyzer.filters import FilterResult
from services.analyzer.cooldown_manager import set_cooldown


async def save_and_publish_signal(
    redis: aioredis.Redis,
    pool: asyncpg.Pool,
    symbol: str,
    price: float,
    result: FilterResult,
) -> None:
    """Save signal to PostgreSQL and publish to Redis Stream."""

    # Save to DB
    signal_id = await pool.fetchval(
        """
        INSERT INTO signals (symbol, direction, price, change_15m, rsi_1h, rsi_15m)
        VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING id
        """,
        symbol,
        result.direction,
        price,
        round(result.change_15m, 4),
        round(result.rsi_1h, 2),
        round(result.rsi_15m, 2),
    )

    logger.info(
        f"Signal #{signal_id} | {result.direction} {symbol} | "
        f"change={result.change_15m:.2f}% RSI_1h={result.rsi_1h:.1f} RSI_15m={result.rsi_15m:.1f}"
    )

    # Set cooldown
    await set_cooldown(redis, symbol)

    # Publish to Redis Stream for chart_builder
    await redis.xadd(STREAM_SIGNALS, {
        "signal_id": str(signal_id),
        "symbol": symbol,
        "direction": result.direction,
        "price": str(price),
        "change_15m": str(round(result.change_15m, 4)),
        "rsi_1h": str(round(result.rsi_1h, 2)),
        "rsi_15m": str(round(result.rsi_15m, 2)),
    })