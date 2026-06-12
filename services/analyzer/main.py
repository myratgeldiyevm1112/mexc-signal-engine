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
    keys = await redis.keys("ready:*")
    symbols = [k.replace("ready:", "") for k in keys]

    if not symbols:
        logger.warning("No ready symbols found in Redis")
        return

    signals_found = 0
    movers: list[tuple[str, float]] = []

    async def process_symbol(symbol):
        if await is_on_cooldown(redis, symbol):
            return None, None
        result = await check_filters(redis, symbol)
        if result is None:
            change_15m = await get_change_15m(redis, symbol)
            return None, (symbol, change_15m) if change_15m is not None else None
        return symbol, result

    # Батчами по 200 чтобы не перегружать Redis
    batch_size = 200
    results = []
    for i in range(0, len(symbols), batch_size):
        batch = symbols[i:i + batch_size]
        tasks = [process_symbol(s) for s in batch]
        batch_results = await asyncio.gather(*tasks)
        results.extend(batch_results)

    for sym, data in results:
        if sym is not None:
            key = CANDLES_KEY.format(symbol=sym, timeframe=TF_15M)
            last = await redis.lindex(key, -1)
            if not last:
                continue
            price = json.loads(last)["close"]
            await save_and_publish_signal(redis, pool, sym, price, data)
            signals_found += 1
        elif data is not None:
            movers.append(data)

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
        start = asyncio.get_event_loop().time()
        try:
            await analyze_all_symbols(redis, pool)
        except Exception as e:
            logger.exception(f"Analysis cycle error: {e}")
        elapsed = asyncio.get_event_loop().time() - start
        sleep_time = max(0, 60 - elapsed)
        logger.debug(f"Cycle took {elapsed:.1f}s, sleeping {sleep_time:.1f}s")
        await asyncio.sleep(sleep_time)


if __name__ == "__main__":
    asyncio.run(main())