import asyncio
import time
import aiohttp
from loguru import logger

from shared.config import settings
from shared.redis_client import get_redis_client
from shared.constants import BOT_START_TIME_KEY
from services.collector.mexc_rest import get_all_usdt_symbols
from services.collector.history_loader import load_all_history
from services.collector.mexc_websocket import run_websocket_manager
from services.collector.health import run_health_server


async def main() -> None:
    logger.info("Starting collector service...")
    redis = get_redis_client()

    # Save bot start time for chart_builder to know how much data is available
    await redis.set(BOT_START_TIME_KEY, int(time.time()))

    # Start health server
    await run_health_server(settings.collector_health_port)

    # Fetch all USDT symbols
    async with aiohttp.ClientSession() as session:
        symbols = await get_all_usdt_symbols(session)

    logger.info(f"Loaded {len(symbols)} symbols, starting history load...")

    # Load historical candles into Redis
    await load_all_history(symbols, redis, batch_size=20, delay_between_batches=2.0)

    logger.info("History loaded. Starting WebSocket manager...")
    await redis.aclose()

    # Start WebSocket connections (runs forever)
    await run_websocket_manager(symbols)


if __name__ == "__main__":
    asyncio.run(main())