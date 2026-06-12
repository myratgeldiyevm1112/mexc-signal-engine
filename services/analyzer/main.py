import asyncio
import json
import asyncpg
from loguru import logger

from shared.config import settings
from shared.redis_client import get_redis_client
from shared.postgres_client import get_postgres_pool
from shared.constants import CANDLES_KEY, TF_15M
from services.analyzer.filters import check_filters, get_change_15m, get_rsi_values
from services.analyzer.cooldown_manager import is_on_cooldown
from services.analyzer.signal_generator import save_and_publish_signal
from services.analyzer.health import run_health_server

TOP_MOVERS_COUNT = 5


async def analyze_all_symbols(redis, pool) -> None:
    """Run filters for all symbols that have data in Redis."""
    # Get all ready symbols
    keys = await redis.keys("ready:*")
    symbols = [k.replace("ready:", "") for k in keys]

    if not symbols:
        logger.warning("No ready symbols found in Redis")
        return

    signals_found = 0
    movers: list[tuple[str, float]] = []  # (symbol, change_15m)

    for symbol in symbols:
        # Skip if on cooldown
        if await is_on_cooldown(redis, symbol):
            continue

        result = await check_filters(redis, symbol)
        if result is None:
            # Lightweight check for top-movers debug log
            change_15m = await get_change_15m(redis, symbol)
            if change_15m is not None:
                movers.append((symbol, change_15m))
            continue

        # Get current price
        key = CANDLES_KEY.format(symbol=symbol, timeframe=TF_15M)
        last = await redis.lindex(key, -1)
        if not last:
            continue
        price = json.loads(last)["close"]

        await save_and_publish_signal(redis, pool, symbol, price, result)
        signals_found += 1

    logger.info(f"Analysis complete: {len(symbols)} symbols checked, {signals_found} signals found")

    # Debug: log top movers by |change_15m| with their RSI values
    if movers:
        movers.sort(key=lambda m: abs(m[1]), reverse=True)
        top = movers[:TOP_MOVERS_COUNT]

        parts = []
        for symbol, change_15m in top:
            rsi_1h, rsi_15m = await get_rsi_values(redis, symbol)
            rsi_1h_str = f"{rsi_1h:.1f}" if rsi_1h is not None else "n/a"
            rsi_15m_str = f"{rsi_15m:.1f}" if rsi_15m is not None else "n/a"
            parts.append(f"{symbol} {change_15m:+.2f}% (RSI1h={rsi_1h_str}, RSI15m={rsi_15m_str})")

        logger.info("Top movers: " + " | ".join(parts))


async def main() -> None:
    logger.info("Starting analyzer service...")

    redis = get_redis_client()
    pool = await get_postgres_pool()

    await run_health_server(settings.analyzer_health_port)

    logger.info("Running analysis every 60 seconds...")
    while True:
        try:
            await analyze_all_symbols(redis, pool)
        except Exception as e:
            logger.error(f"Analysis cycle error: {e}")
        await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(main())