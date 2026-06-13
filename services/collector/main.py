import asyncio
import signal
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

    stop_event = asyncio.Event()

    def _handle_sigterm():
        logger.info("SIGTERM received, shutting down collector...")
        stop_event.set()

    asyncio.get_event_loop().add_signal_handler(signal.SIGTERM, _handle_sigterm)
    asyncio.get_event_loop().add_signal_handler(signal.SIGINT, _handle_sigterm)

    await redis.set(BOT_START_TIME_KEY, int(time.time()))
    await run_health_server(settings.collector_health_port)

    async with aiohttp.ClientSession() as session:
        symbols = await get_all_usdt_symbols(session)

    logger.info(f"Loaded {len(symbols)} symbols, starting history load...")
    await load_all_history(symbols, redis, batch_size=5, delay_between_batches=1.0)

    logger.info("History loaded. Starting WebSocket manager...")
    await redis.aclose()

    ws_task = asyncio.create_task(run_websocket_manager(symbols))
    await stop_event.wait()

    logger.info("Stopping WebSocket manager...")
    ws_task.cancel()
    try:
        await ws_task
    except asyncio.CancelledError:
        pass

    logger.info("Collector stopped.")


if __name__ == "__main__":
    asyncio.run(main())