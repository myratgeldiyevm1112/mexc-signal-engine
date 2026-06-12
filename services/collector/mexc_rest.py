import asyncio
import aiohttp
from loguru import logger

MEXC_FUTURES_REST_URL = "https://contract.mexc.com"


async def get_all_usdt_symbols(session: aiohttp.ClientSession) -> list[str]:
    """Fetch all active USDT-margined futures contracts from MEXC."""
    url = f"{MEXC_FUTURES_REST_URL}/api/v1/contract/detail"
    logger.info("Fetching all USDT futures contracts from MEXC...")

    async with session.get(url) as response:
        response.raise_for_status()
        payload = await response.json()

    symbols = [
        c["symbol"]
        for c in payload["data"]
        if c["symbol"].endswith("_USDT")
    ]
    logger.info(f"Found {len(symbols)} USDT futures contracts")
    return symbols


async def get_historical_klines(
    session: aiohttp.ClientSession,
    symbol: str,
    interval: str,
    limit: int = 200,
    retries: int = 4,
) -> list[dict]:
    """Fetch historical klines for a futures contract, with retry on empty/rate-limited response."""
    url = f"{MEXC_FUTURES_REST_URL}/api/v1/contract/kline/{symbol}"
    params = {"interval": interval}

    for attempt in range(retries):
        async with session.get(url, params=params) as response:
            response.raise_for_status()
            payload = await response.json()

        data = payload.get("data")
        if data and data.get("time"):
            candles = [
                {
                    "timestamp": int(t) * 1000,
                    "open": float(o),
                    "high": float(h),
                    "low": float(l),
                    "close": float(c),
                    "volume": float(v),
                }
                for t, o, h, l, c, v in zip(
                    data["time"], data["open"], data["high"],
                    data["low"], data["close"], data["vol"],
                )
            ]
            return candles[-limit:]

        # Empty response — likely rate limited, back off and retry
        await asyncio.sleep(0.5 * (attempt + 1))

    logger.warning(f"No kline data for {symbol} ({interval}) after {retries} attempts")
    return []