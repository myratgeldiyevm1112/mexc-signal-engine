"""
backtester/run.py
Entry point: load symbols, run backtest, print report.
"""
import asyncio
from pathlib import Path
from loguru import logger

from backtester.data_loader import get_all_symbols, DATA_DIR
from backtester.engine import run_all
from backtester.report import generate_report
from backtester.money_management import simulate, print_report


def get_downloaded_symbols() -> list[str]:
    """Get symbols that already have downloaded data."""
    path = DATA_DIR / "15m"
    if not path.exists():
        return []
    return [f.stem for f in path.glob("*.csv")]


async def main():
    symbols = get_downloaded_symbols()

    if not symbols:
        logger.info("No data found, downloading first...")
        symbols = await get_all_symbols()
        from backtester.data_loader import download_all
        await download_all(symbols)
        symbols = get_downloaded_symbols()

    logger.info(f"Running backtest on {len(symbols)} symbols...")
    df = run_all(symbols)
    generate_report(df)
    mm_report = simulate(df)
    print_report(mm_report)


if __name__ == "__main__":
    asyncio.run(main())