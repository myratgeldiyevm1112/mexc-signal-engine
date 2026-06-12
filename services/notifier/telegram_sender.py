"""
services/notifier/telegram_sender.py
Sends chart photo + caption to Telegram with retries.
"""

import asyncio

from aiogram import Bot
from aiogram.types import BufferedInputFile
from aiogram.exceptions import TelegramAPIError
from loguru import logger

from shared.config import settings

MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 3


async def send_signal_photo(bot: Bot, png_bytes: bytes, caption: str, symbol: str) -> int | None:
    """
    Sends a photo with caption to the configured Telegram chat.
    Retries up to MAX_RETRIES times on failure.
    Returns the Telegram message_id on success, or None on failure.
    """
    photo = BufferedInputFile(png_bytes, filename=f"{symbol}.png")

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            msg = await bot.send_photo(
                chat_id=settings.telegram_chat_id,
                photo=photo,
                caption=caption,
                parse_mode="HTML",
            )
            logger.info(f"Sent signal for {symbol} to Telegram (msg_id={msg.message_id})")
            return msg.message_id
        except TelegramAPIError as e:
            logger.warning(f"Telegram send attempt {attempt}/{MAX_RETRIES} failed for {symbol}: {e}")
            if attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_DELAY_SECONDS)

    logger.error(f"Failed to send Telegram message for {symbol} after {MAX_RETRIES} attempts")
    return None
