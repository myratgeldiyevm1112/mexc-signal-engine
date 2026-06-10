import asyncio
import aiohttp
from loguru import logger


MEXC_REST_URL = "https://api.mexc.com"


async def get_all_usdt_symbols(session: aiohttp.ClientSession) -> list[str]:
    """Fetches a list of all active USDT trading pairs from MEXC."""
    url = f"{MEXC_REST_URL}/api/v3/exchangeInfo"
    logger.info("Fetching all USDT symbols from MEXC...")

    async with session.get(url) as response:
        response.raise_for_status()
        data = await response.json()

    symbols = [
        s["symbol"]
        for s in data["symbols"]
        if s["symbol"].endswith("USDT") and s["status"] == "1"
    ]

    logger.info(f"Found {len(symbols)} USDT symbols")
    return symbols


async def get_historical_klines(
    session: aiohttp.ClientSession,
    symbol: str,
    interval: str,
    limit: int = 200,
) -> list[dict]:
    """
    Fetches historical candles for a single symbol.

    interval: "1m", "5m", "15m", "1h"
    limit: number of candles (maximum 1000)
    """
    url = f"{MEXC_REST_URL}/api/v3/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}

    async with session.get(url, params=params) as response:
        response.raise_for_status()
        data = await response.json()

    # MEXC returns a list of lists:
    # [timestamp, open, high, low, close, volume, ...]
    candles = []
    for item in data:
        candles.append({
            "timestamp": int(item[0]),
            "open":      float(item[1]),
            "high":      float(item[2]),
            "low":       float(item[3]),
            "close":     float(item[4]),
            "volume":    float(item[5]),
        })

    return candles