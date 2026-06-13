import asyncio
import signal
import json

from redis.exceptions import TimeoutError as RedisTimeoutError
from loguru import logger

from shared.config import settings
from shared.redis_client import get_redis_client
from shared.constants import CANDLES_KEY, STREAM_SIGNALS, STREAM_CHART_READY, TF_5M
from services.chart_builder.chart_renderer import render_chart
from services.chart_builder.minio_uploader import get_minio_client, ensure_bucket, upload_chart
from services.chart_builder.health import run_health_server

CONSUMER_GROUP = "chart_builder_group"
CONSUMER_NAME = "chart_builder-1"


async def _ensure_consumer_group(redis) -> None:
    try:
        await redis.xgroup_create(STREAM_SIGNALS, CONSUMER_GROUP, id="0", mkstream=True)
        logger.info(f"Created consumer group '{CONSUMER_GROUP}' on {STREAM_SIGNALS}")
    except Exception as e:
        if "BUSYGROUP" not in str(e):
            raise


async def _get_candles_5m(redis, symbol: str) -> list[dict]:
    key = CANDLES_KEY.format(symbol=symbol, timeframe=TF_5M)
    raw = await redis.lrange(key, 0, -1)
    return [json.loads(c) for c in raw]


async def _process_signal(redis, minio_client, fields: dict) -> None:
    symbol = fields["symbol"]
    direction = fields["direction"]
    signal_id = fields["signal_id"]
    price = float(fields["price"])
    change_15m = float(fields["change_15m"])
    rsi_1h = float(fields["rsi_1h"])
    rsi_15m = float(fields["rsi_15m"])

    logger.info(f"Building chart for {symbol} ({direction}) signal_id={signal_id}")

    candles_5m = await _get_candles_5m(redis, symbol)
    if not candles_5m:
        logger.warning(f"No 5m candles for {symbol}, skipping chart")
        return

    png_bytes = render_chart(
        symbol=symbol,
        candles_5m=candles_5m,
        current_price=price,
        direction=direction,
        change_15m=change_15m,
        rsi_1h=rsi_1h,
        rsi_15m=rsi_15m,
    )

    chart_url = upload_chart(minio_client, symbol, png_bytes)

    await redis.xadd(STREAM_CHART_READY, {
        "signal_id": signal_id,
        "symbol": symbol,
        "direction": direction,
        "chart_url": chart_url,
        "price": price,
        "change_15m": change_15m,
        "rsi_1h": rsi_1h,
        "rsi_15m": rsi_15m,
    })
    logger.info(f"Chart ready for {symbol}: {chart_url}")


async def main() -> None:
    logger.info("Starting chart_builder service...")

    redis = get_redis_client()
    minio_client = get_minio_client()
    ensure_bucket(minio_client)

    stop_event = asyncio.Event()

    def _handle_sigterm():
        logger.info("SIGTERM received, shutting down chart_builder...")
        stop_event.set()

    asyncio.get_event_loop().add_signal_handler(signal.SIGTERM, _handle_sigterm)
    asyncio.get_event_loop().add_signal_handler(signal.SIGINT, _handle_sigterm)

    await _ensure_consumer_group(redis)
    await run_health_server(settings.chart_builder_health_port)

    logger.info(f"Listening on {STREAM_SIGNALS}...")
    while not stop_event.is_set():
        try:
            resp = await redis.xreadgroup(
                groupname=CONSUMER_GROUP,
                consumername=CONSUMER_NAME,
                streams={STREAM_SIGNALS: ">"},
                count=10,
                block=5000,
            )
            if not resp:
                continue
            for _stream_name, messages in resp:
                for msg_id, fields in messages:
                    try:
                        await _process_signal(redis, minio_client, fields)
                    except Exception as e:
                        logger.error(f"Error processing signal {msg_id}: {e}")
                    finally:
                        await redis.xack(STREAM_SIGNALS, CONSUMER_GROUP, msg_id)
        except RedisTimeoutError:
            continue
        except Exception as e:
            logger.error(f"chart_builder loop error: {e}")
            await asyncio.sleep(5)

    await redis.aclose()
    logger.info("chart_builder stopped.")


if __name__ == "__main__":
    asyncio.run(main())