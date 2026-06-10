from shared.config import settings
import asyncio
import json
import time
import websockets
from loguru import logger

from shared.config import settings
from shared.constants import CANDLES_KEY, TF_1H, TF_15M, TF_5M
from shared.redis_client import get_redis_client

MEXC_WS_URL = "wss://wbs.mexc.com/ws"
PING_INTERVAL = 30  # seconds
RECONNECT_DELAY_BASE = 2  # seconds, doubles on each retry
RECONNECT_DELAY_MAX = 60  # seconds


def _build_subscribe_msg(symbols: list[str]) -> dict:
    """Build MEXC WebSocket subscription message for kline streams."""
    params = []
    for symbol in symbols:
        params.append(f"spot@public.kline.v3.api@{symbol}@Min1")
        params.append(f"spot@public.kline.v3.api@{symbol}@Min5")
        params.append(f"spot@public.kline.v3.api@{symbol}@Min15")
        params.append(f"spot@public.kline.v3.api@{symbol}@Min60")
    return {"method": "SUBSCRIPTION", "params": params}


def _parse_kline_message(msg: dict) -> tuple[str, str, dict] | None:
    """
    Parse incoming kline message from MEXC WebSocket.
    Returns (symbol, timeframe, candle_dict) or None if not a kline message.
    """
    if msg.get("c") != "spot@public.kline.v3.api":
        return None

    data = msg.get("d", {})
    k = data.get("k", {})
    if not k:
        return None

    symbol = msg.get("s", "")
    interval = k.get("i", "")

    tf_map = {"Min1": "1m", "Min5": TF_5M, "Min15": TF_15M, "Min60": TF_1H}
    timeframe = tf_map.get(interval)
    if not timeframe:
        return None

    candle = {
        "timestamp": int(k.get("t", 0)),
        "open":      float(k.get("o", 0)),
        "high":      float(k.get("h", 0)),
        "low":       float(k.get("l", 0)),
        "close":     float(k.get("c", 0)),
        "volume":    float(k.get("v", 0)),
    }
    return symbol, timeframe, candle


BUFFER_SIZE_MAP = {
    "1m":   200,
    TF_5M:  settings.candles_5min_buffer,
    TF_15M: settings.candles_15min_buffer,
    TF_1H:  settings.candles_1h_buffer,
}


async def _handle_connection(symbols: list[str], conn_id: int) -> None:
    """Handle a single WebSocket connection for a batch of symbols."""
    redis = get_redis_client()
    delay = RECONNECT_DELAY_BASE

    while True:
        try:
            logger.info(f"[WS-{conn_id}] Connecting for {len(symbols)} symbols...")
            proxy = settings.http_proxy or None
            async with websockets.connect(MEXC_WS_URL, ping_interval=None, proxy=proxy) as ws:
                # Subscribe to all symbols in this batch
                await ws.send(json.dumps(_build_subscribe_msg(symbols)))
                logger.info(f"[WS-{conn_id}] Subscribed, listening...")
                delay = RECONNECT_DELAY_BASE  # reset on success

                last_ping = time.time()

                async for raw in ws:
                    # Send ping periodically to keep connection alive
                    if time.time() - last_ping > PING_INTERVAL:
                        await ws.send(json.dumps({"method": "PING"}))
                        last_ping = time.time()

                    msg = json.loads(raw)
                    result = _parse_kline_message(msg)
                    if result is None:
                        continue

                    symbol, timeframe, candle = result
                    buffer_size = BUFFER_SIZE_MAP.get(timeframe, 200)
                    redis_key = CANDLES_KEY.format(symbol=symbol, timeframe=timeframe)

                    # Update candle buffer in Redis
                    pipe = redis.pipeline()
                    pipe.rpush(redis_key, json.dumps(candle))
                    pipe.ltrim(redis_key, -buffer_size, -1)
                    await pipe.execute()

        except Exception as e:
            logger.warning(f"[WS-{conn_id}] Disconnected: {type(e).__name__}: {e}. Retrying in {delay}s...")
            await asyncio.sleep(delay)
            delay = min(delay * 2, RECONNECT_DELAY_MAX)
        finally:
            await redis.aclose()
            redis = get_redis_client()


async def run_websocket_manager(symbols: list[str]) -> None:
    """
    Launch multiple WebSocket connections to cover all symbols.
    Each connection handles up to MEXC_SYMBOLS_PER_WS_CONNECTION symbols.
    """
    batch_size = settings.mexc_symbols_per_ws_connection
    batches = [symbols[i:i + batch_size] for i in range(0, len(symbols), batch_size)]
    logger.info(f"Starting {len(batches)} WebSocket connections for {len(symbols)} symbols")

    tasks = [
        asyncio.create_task(_handle_connection(batch, conn_id=i))
        for i, batch in enumerate(batches)
    ]
    await asyncio.gather(*tasks)