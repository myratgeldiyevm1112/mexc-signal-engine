import asyncio

import redis.exceptions
from aiogram import Bot
from loguru import logger

from shared.config import settings
from shared.redis_client import get_redis_client
from shared.postgres_client import get_postgres_pool
from shared.constants import STREAM_CHART_READY
from services.notifier.minio_downloader import get_minio_client, download_chart
from services.notifier.message_formatter import format_signal_message
from services.notifier.telegram_sender import send_signal_photo
from services.notifier.health import run_health_server

CONSUMER_GROUP = "notifier_group"
CONSUMER_NAME = "notifier-1"


async def _ensure_consumer_group(redis) -> None:
    try:
        await redis.xgroup_create(STREAM_CHART_READY, CONSUMER_GROUP, id="0", mkstream=True)
        logger.info(f"Created consumer group '{CONSUMER_GROUP}' on {STREAM_CHART_READY}")
    except Exception as e:
        if "BUSYGROUP" not in str(e):
            raise


async def _process_message(bot: Bot, minio_client, pool, fields: dict) -> None:
    signal_id = int(fields["signal_id"])
    symbol = fields["symbol"]
    direction = fields["direction"]
    chart_url = fields["chart_url"]
    price = float(fields["price"])
    change_15m = float(fields["change_15m"])
    rsi_1h = float(fields["rsi_1h"])
    rsi_15m = float(fields["rsi_15m"])

    logger.info(f"Notifying for {symbol} ({direction}) signal_id={signal_id}")

    png_bytes = download_chart(minio_client, chart_url)

    caption = format_signal_message(
        symbol=symbol,
        direction=direction,
        price=price,
        change_15m=change_15m,
        rsi_1h=rsi_1h,
        rsi_15m=rsi_15m,
    )

    msg_id = await send_signal_photo(bot, png_bytes, caption, symbol)

    if msg_id is not None:
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE signals SET telegram_sent = TRUE, telegram_msg_id = $1 WHERE id = $2",
                msg_id, signal_id,
            )
        logger.info(f"Updated signal {signal_id} as sent (msg_id={msg_id})")
    else:
        logger.error(f"Signal {signal_id} ({symbol}) was NOT sent to Telegram")


async def main() -> None:
    logger.info("Starting notifier service...")

    redis = get_redis_client()
    pool = await get_postgres_pool()
    minio_client = get_minio_client()
    bot = Bot(token=settings.telegram_bot_token)

    await _ensure_consumer_group(redis)
    await run_health_server(settings.notifier_health_port)

    logger.info(f"Listening on {STREAM_CHART_READY}...")
    while True:
        try:
            resp = await redis.xreadgroup(
                groupname=CONSUMER_GROUP,
                consumername=CONSUMER_NAME,
                streams={STREAM_CHART_READY: ">"},
                count=10,
                block=5000,
            )
            if not resp:
                continue

            for _stream_name, messages in resp:
                for msg_id, fields in messages:
                    try:
                        await _process_message(bot, minio_client, pool, fields)
                    except Exception as e:
                        logger.error(f"Error processing chart_ready message {msg_id}: {e}")
                    finally:
                        await redis.xack(STREAM_CHART_READY, CONSUMER_GROUP, msg_id)

        except redis.exceptions.TimeoutError:
            # Expected when no messages arrive within block window; just retry.
            continue
        except Exception as e:
            logger.error(f"notifier loop error: {e}")
            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())