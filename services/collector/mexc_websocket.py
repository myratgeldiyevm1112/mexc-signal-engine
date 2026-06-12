import asyncio
import json
import time
import websockets
from loguru import logger

from shared.config import settings
from shared.constants import CANDLES_KEY, TF_1H, TF_15M, TF_5M, MEXC_INTERVAL_MAP
from shared.redis_client import get_redis_client

MEXC_WS_URL = "wss://contract.mexc.com/edge"
PING_INTERVAL = 15  # seconds
RECONNECT_DELAY_BASE = 2
RECONNECT_DELAY_MAX = 60

SUBSCRIBE_INTERVALS = [TF_5M, TF_15M, TF_1H]
INTERVAL_TO_TF = {MEXC_INTERVAL_MAP[tf]: tf for tf in SUBSCRIBE_INTERVALS}

BUFFER_SIZE_MAP = {
    TF_5M:  settings.candles_5min_buffer,
    TF_15M: settings.candles_15min_buffer,
    TF_1H:  settings.candles_1h_buffer,
}


def _build_subscribe_messages(symbols: list[str]) -> list[dict]:
    """Build MEXC futures kline subscription messages (one per symbol/interval)."""
    messages = []
    for symbol in symbols:
        for tf in SUBSCRIBE_INTERVALS:
            interval = MEXC_INTERVAL_MAP[tf]
            messages.append({
                "method": "sub.kline",
                "param": {"symbol": symbol, "interval": interval},
            })
    return messages


def _parse_kline_message(msg: dict) -> tuple[str, str, dict] | None:
    """Parse incoming kline push message from MEXC Futures WebSocket."""
    if msg.get("channel") != "push.kline":
        return None

    data = msg.get("data", {})
    if not data:
        return None

    symbol = data.get("symbol", "")
    interval = data.get("interval", "")
    timeframe = INTERVAL_TO_TF.get(interval)
    if not timeframe:
        return None

    candle = {
        "timestamp": int(data.get("t", 0)) * 1000,
        "open":      float(data.get("o", 0)),
        "high":      float(data.get("h", 0)),
        "low":       float(data.get("l", 0)),
        "close":     float(data.get("c", 0)),
        "volume":    float(data.get("q", 0)),
    }
    return symbol, timeframe, candle


async def _handle_connection(symbols: list[str], conn_id: int) -> None:
    """Handle a single WebSocket connection for a batch of symbols."""
    redis = get_redis_client()
    delay = RECONNECT_DELAY_BASE

    while True:
        try:
            logger.info(f"[WS-{conn_id}] Connecting for {len(symbols)} symbols...")
            async with websockets.connect(MEXC_WS_URL, ping_interval=None) as ws:
                for sub_msg in _build_subscribe_messages(symbols):
                    await ws.send(json.dumps(sub_msg))
                    await asyncio.sleep(0.05)

                logger.info(f"[WS-{conn_id}] Subscribed, listening...")
                delay = RECONNECT_DELAY_BASE

                last_ping = time.time()

                async for raw in ws:
                    if time.time() - last_ping > PING_INTERVAL:
                        await ws.send(json.dumps({"method": "ping"}))
                        last_ping = time.time()

                    msg = json.loads(raw)

                    if msg.get("channel") == "pong":
                        continue

                    result = _parse_kline_message(msg)
                    if result is None:
                        continue

                    symbol, timeframe, candle = result
                    buffer_size = BUFFER_SIZE_MAP.get(timeframe, 200)
                    redis_key = CANDLES_KEY.format(symbol=symbol, timeframe=timeframe)

                    last_raw = await redis.lindex(redis_key, -1)
                    if last_raw is not None:
                        last_candle = json.loads(last_raw)
                        if last_candle.get("timestamp") == candle["timestamp"]:
                            # Same (still-open) candle — replace last entry instead of appending
                            pipe = redis.pipeline()
                            pipe.rpop(redis_key)
                            pipe.rpush(redis_key, json.dumps(candle))
                            pipe.ltrim(redis_key, -buffer_size, -1)
                            await pipe.execute()
                            continue

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
    batch_size = settings.mexc_symbols_per_ws_connection
    batches = [symbols[i:i + batch_size] for i in range(0, len(symbols), batch_size)]
    logger.info(f"Starting {len(batches)} WebSocket connections for {len(symbols)} symbols")

    tasks = [
        asyncio.create_task(_handle_connection(batch, conn_id=i))
        for i, batch in enumerate(batches)
    ]
    await asyncio.gather(*tasks)