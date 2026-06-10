import aiohttp
from loguru import logger
from shared.config import settings

MEXC_REST_URL = "https://api.mexc.com"


def _get_connector() -> aiohttp.TCPConnector | None:
    return None


def _get_proxy() -> str | None:
    return settings.http_proxy or None


async def get_all_usdt_symbols(session: aiohttp.ClientSession) -> list[str]:
    """Fetch all active USDT trading pairs from MEXC."""
    url = f"{MEXC_REST_URL}/api/v3/exchangeInfo"
    logger.info("Fetching all USDT symbols from MEXC...")

    async with session.get(url, proxy=_get_proxy()) as response:
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
    """Fetch historical klines for a symbol."""
    url = f"{MEXC_REST_URL}/api/v3/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}

    async with session.get(url, params=params, proxy=_get_proxy()) as response:
        response.raise_for_status()
        data = await response.json()

    return [
        {
            "timestamp": int(item[0]),
            "open":      float(item[1]),
            "high":      float(item[2]),
            "low":       float(item[3]),
            "close":     float(item[4]),
            "volume":    float(item[5]),
        }
        for item in data
    ]