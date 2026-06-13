import asyncio
import signal
from datetime import datetime, timezone

import aiohttp
from aiogram import Bot
from loguru import logger

from shared.config import settings

CHECK_INTERVAL = 60  # seconds between checks
FAIL_THRESHOLD = 2   # consecutive failures before alert

SERVICES = {
    "collector":     f"http://collector:{settings.collector_health_port}/health",
    "analyzer":      f"http://analyzer:{settings.analyzer_health_port}/health",
    "chart_builder": f"http://chart_builder:{settings.chart_builder_health_port}/health",
    "notifier":      f"http://notifier:{settings.notifier_health_port}/health",
}


async def check_service(session: aiohttp.ClientSession, name: str, url: str) -> bool:
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
            return resp.status == 200
    except Exception:
        return False


async def send_alert(bot: Bot, text: str) -> None:
    try:
        await bot.send_message(
            chat_id=settings.telegram_chat_id,
            text=text,
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(f"Failed to send alert: {e}")


async def main() -> None:
    logger.info("Starting watchdog service...")

    bot = Bot(token=settings.telegram_bot_token)
    stop_event = asyncio.Event()

    def _handle_sigterm():
        logger.info("SIGTERM received, shutting down watchdog...")
        stop_event.set()

    asyncio.get_event_loop().add_signal_handler(signal.SIGTERM, _handle_sigterm)
    asyncio.get_event_loop().add_signal_handler(signal.SIGINT, _handle_sigterm)

    # Track consecutive failures per service
    failures: dict[str, int] = {name: 0 for name in SERVICES}
    alerted: dict[str, bool] = {name: False for name in SERVICES}

    await send_alert(bot, "✅ <b>Watchdog started</b> — monitoring all services.")

    async with aiohttp.ClientSession() as session:
        while not stop_event.is_set():
            for name, url in SERVICES.items():
                ok = await check_service(session, name, url)

                if ok:
                    if alerted[name]:
                        # Service recovered
                        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
                        await send_alert(
                            bot,
                            f"✅ <b>{name}</b> recovered\n📅 {now}"
                        )
                        logger.info(f"{name} recovered")
                        alerted[name] = False
                    failures[name] = 0
                else:
                    failures[name] += 1
                    logger.warning(f"{name} health check failed ({failures[name]}/{FAIL_THRESHOLD})")

                    if failures[name] >= FAIL_THRESHOLD and not alerted[name]:
                        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
                        await send_alert(
                            bot,
                            f"🚨 <b>{name} is DOWN</b>\n"
                            f"❌ Failed {failures[name]} checks in a row\n"
                            f"📅 {now}"
                        )
                        alerted[name] = True
                        logger.error(f"Alert sent: {name} is DOWN")

            try:
                await asyncio.wait_for(stop_event.wait(), timeout=CHECK_INTERVAL)
            except asyncio.TimeoutError:
                pass

    await bot.session.close()
    logger.info("Watchdog stopped.")


if __name__ == "__main__":
    asyncio.run(main())