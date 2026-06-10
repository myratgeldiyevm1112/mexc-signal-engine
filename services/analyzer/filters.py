import json
from dataclasses import dataclass

import redis.asyncio as aioredis

from shared.config import settings
from shared.constants import CANDLES_KEY, READY_KEY, TF_1H, TF_15M
from services.analyzer.rsi_calculator import calculate_rsi


@dataclass
class FilterResult:
    passed: bool
    direction: str | None  # "LONG", "SHORT", or None
    change_15m: float
    rsi_1h: float
    rsi_15m: float


async def _get_closes(redis: aioredis.Redis, symbol: str, timeframe: str) -> list[float]:
    """Read candle closes from Redis buffer."""
    key = CANDLES_KEY.format(symbol=symbol, timeframe=timeframe)
    raw = await redis.lrange(key, 0, -1)
    return [json.loads(c)["close"] for c in raw]


async def _get_price_15m_ago(redis: aioredis.Redis, symbol: str) -> float | None:
    """Get closing price from 15 minutes ago (second to last 15m candle)."""
    key = CANDLES_KEY.format(symbol=symbol, timeframe=TF_15M)
    raw = await redis.lindex(key, -2)
    if not raw:
        return None
    return json.loads(raw)["close"]


async def check_filters(redis: aioredis.Redis, symbol: str) -> FilterResult | None:
    """
    Run all 3 filters for a symbol.
    Returns FilterResult if signal found, None otherwise.
    """
    # Skip if historical data not ready
    ready = await redis.get(READY_KEY.format(symbol=symbol))
    if not ready:
        return None

    # Get current price
    closes_15m = await _get_closes(redis, symbol, TF_15M)
    if len(closes_15m) < 16:
        return None

    current_price = closes_15m[-1]
    price_15m_ago = await _get_price_15m_ago(redis, symbol)
    if not price_15m_ago or price_15m_ago == 0:
        return None

    # Filter 1: price change >= threshold
    change_15m = (current_price - price_15m_ago) / price_15m_ago * 100
    threshold = settings.filter_price_change_percent
    if abs(change_15m) < threshold:
        return None

    # Filter 2: RSI 1h
    closes_1h = await _get_closes(redis, symbol, TF_1H)
    rsi_1h = calculate_rsi(closes_1h, settings.filter_rsi_period)
    if rsi_1h is None:
        return None

    # Filter 3: RSI 15m
    rsi_15m = calculate_rsi(closes_15m, settings.filter_rsi_period)
    if rsi_15m is None:
        return None

    overbought = settings.filter_rsi_overbought
    oversold = settings.filter_rsi_oversold

    # Check LONG: price up + both RSI overbought
    if change_15m >= threshold and rsi_1h > overbought and rsi_15m > overbought:
        return FilterResult(True, "LONG", change_15m, rsi_1h, rsi_15m)

    # Check SHORT: price down + both RSI oversold
    if change_15m <= -threshold and rsi_1h < oversold and rsi_15m < oversold:
        return FilterResult(True, "SHORT", change_15m, rsi_1h, rsi_15m)

    return None