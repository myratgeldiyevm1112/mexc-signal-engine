import asyncio
import json
import aiohttp
import redis.asyncio as aioredis
from loguru import logger

from shared.config import settings
from shared.constants import CANDLES_KEY, READY_KEY, TF_5M, TF_15M, TF_1H, MEXC_INTERVAL_MAP
from services.collector.mexc_rest import get_historical_klines

TIMEFRAMES = {
    TF_5M:  settings.candles_5min_buffer,
    TF_15M: settings.candles_15min_buffer,
    TF_1H:  settings.candles_1h_buffer,
}


async def load_symbol_history(
    session: aiohttp.ClientSession,
    redis: aioredis.Redis,
    symbol: str,
) -> bool:
    """Load historical candles for one symbol across all timeframes."""
    try:
        for tf, buffer_size in TIMEFRAMES.items():
            candles = await get_historical_klines(
                session=session,
                symbol=symbol,
                interval=MEXC_INTERVAL_MAP[tf],
                limit=buffer_size,
            )
            if not candles:
                continue

            redis_key = CANDLES_KEY.format(symbol=symbol, timeframe=tf)
            await redis.delete(redis_key)
            pipe = redis.pipeline()
            for candle in candles:
                pipe.rpush(redis_key, json.dumps(candle))
            pipe.ltrim(redis_key, -buffer_size, -1)
            await pipe.execute()

            # Small delay between timeframes to avoid rate limit
            await asyncio.sleep(0.3)

        await redis.set(READY_KEY.format(symbol=symbol), "1")
        return True

    except Exception as e:
        logger.error(f"Failed to load history for {symbol}: {e}")
        return False


async def load_all_history(
    symbols: list[str],
    redis: aioredis.Redis,
    batch_size: int = 10,
    delay_between_batches: float = 3.0,
) -> None:
    """Load historical candles for all symbols in batches."""
    total = len(symbols)
    loaded = 0
    failed = 0

    logger.info(f"Starting history load for {total} symbols, batch_size={batch_size}")

    async with aiohttp.ClientSession() as session:
        for i in range(0, total, batch_size):
            batch = symbols[i:i + batch_size]
            tasks = [load_symbol_history(session, redis, symbol) for symbol in batch]
            results = await asyncio.gather(*tasks)

            batch_loaded = sum(results)
            batch_failed = len(results) - batch_loaded
            loaded += batch_loaded
            failed += batch_failed

            logger.info(
                f"History progress: {min(i + batch_size, total)}/{total} "
                f"| loaded={loaded} failed={failed}"
            )

            if i + batch_size < total:
                await asyncio.sleep(delay_between_batches)

    logger.info(f"History load complete: {loaded} loaded, {failed} failed")