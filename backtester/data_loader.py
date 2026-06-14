"""
backtester/data_loader.py
Downloads historical klines from MEXC Futures REST API and saves to CSV.
Supports paginated download to get up to 90 days of history.
"""
import asyncio
import aiohttp
import pandas as pd
from pathlib import Path
from loguru import logger
import datetime

MEXC_FUTURES_REST_URL = "https://contract.mexc.com"
DATA_DIR = Path("backtester/data")

INTERVALS = {
    "5m":  "Min5",
    "15m": "Min15",
    "1h":  "Min60",
}

CANDLES_PER_REQUEST = 2000
DAYS_PER_REQUEST = 20  # ~2000 x 15m = 20 days
TARGET_DAYS = 90       # how many days of history we want


async def fetch_klines_page(
    session: aiohttp.ClientSession,
    symbol: str,
    interval: str,
    start_ts: int | None = None,
) -> list[dict]:
    url = f"{MEXC_FUTURES_REST_URL}/api/v1/contract/kline/{symbol}"
    params = {"interval": interval}
    if start_ts:
        params["start"] = start_ts

    for attempt in range(4):
        try:
            async with session.get(url, params=params) as resp:
                resp.raise_for_status()
                payload = await resp.json()

            data = payload.get("data")
            if data and data.get("time"):
                return [
                    {
                        "timestamp": int(t) * 1000,
                        "open":   float(o),
                        "high":   float(h),
                        "low":    float(l),
                        "close":  float(c),
                        "volume": float(v),
                    }
                    for t, o, h, l, c, v in zip(
                        data["time"], data["open"], data["high"],
                        data["low"], data["close"], data["vol"],
                    )
                ]
            await asyncio.sleep(0.5 * (attempt + 1))

        except Exception as e:
            logger.warning(f"{symbol} {interval} attempt {attempt+1} failed: {e}")
            await asyncio.sleep(0.5 * (attempt + 1))

    return []


async def fetch_klines_full(
    session: aiohttp.ClientSession,
    symbol: str,
    interval: str,
    target_days: int = TARGET_DAYS,
) -> list[dict]:
    """Fetch multiple pages going back target_days."""
    all_candles: dict[int, dict] = {}

    now = datetime.datetime.now(datetime.timezone.utc)
    # Calculate how many pages we need
    pages = (target_days // DAYS_PER_REQUEST) + 1

    for page in range(pages):
        days_back = page * DAYS_PER_REQUEST
        start_dt = now - datetime.timedelta(days=days_back + DAYS_PER_REQUEST)
        start_ts = int(start_dt.timestamp())

        candles = await fetch_klines_page(session, symbol, interval, start_ts)
        for c in candles:
            all_candles[c["timestamp"]] = c

        await asyncio.sleep(0.2)

    # Sort by timestamp
    sorted_candles = sorted(all_candles.values(), key=lambda x: x["timestamp"])
    return sorted_candles


def save_csv(symbol: str, interval: str, candles: list[dict]) -> None:
    path = DATA_DIR / interval
    path.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(candles)
    df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df = df.drop_duplicates(subset=["timestamp"]).sort_values("timestamp")
    df.to_csv(path / f"{symbol}.csv", index=False)


def load_csv(symbol: str, interval: str) -> pd.DataFrame | None:
    path = DATA_DIR / interval / f"{symbol}.csv"
    if not path.exists():
        return None
    df = pd.read_csv(path)
    df["datetime"] = pd.to_datetime(df["datetime"], utc=True)
    return df


async def download_all(symbols: list[str], batch_size: int = 3) -> None:
    """Download 15m and 1h klines for all symbols (90 days)."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    total = len(symbols)
    logger.info(f"Downloading {TARGET_DAYS} days of data for {total} symbols...")

    async with aiohttp.ClientSession() as session:
        for interval_name, interval_code in INTERVALS.items():
            logger.info(f"Downloading {interval_name} candles ({TARGET_DAYS} days)...")
            downloaded = 0

            for i in range(0, total, batch_size):
                batch = symbols[i:i + batch_size]
                tasks = [
                    fetch_klines_full(session, s, interval_code, TARGET_DAYS)
                    for s in batch
                ]
                results = await asyncio.gather(*tasks)

                for symbol, candles in zip(batch, results):
                    if candles:
                        save_csv(symbol, interval_name, candles)
                        downloaded += 1
                    else:
                        logger.warning(f"No data for {symbol} {interval_name}")

                logger.info(f"{interval_name}: {min(i + batch_size, total)}/{total}")
                await asyncio.sleep(1.0)

            logger.info(f"{interval_name} done: {downloaded}/{total} saved")


async def get_all_symbols() -> list[str]:
    async with aiohttp.ClientSession() as session:
        url = f"{MEXC_FUTURES_REST_URL}/api/v1/contract/detail"
        async with session.get(url) as resp:
            payload = await resp.json()
    return [c["symbol"] for c in payload["data"] if c["symbol"].endswith("_USDT")]


if __name__ == "__main__":
    async def main():
        symbols = await get_all_symbols()
        logger.info(f"Found {len(symbols)} symbols")
        await download_all(symbols, batch_size=3)
        logger.info("Download complete! Data saved to backtester/data/")

    asyncio.run(main())