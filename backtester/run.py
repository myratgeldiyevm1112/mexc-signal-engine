"""
backtester/run.py
Entry point: runs backtest for both 5m and 15m, compares results.
"""
import asyncio
from pathlib import Path
from loguru import logger

from backtester.data_loader import get_all_symbols, DATA_DIR
from backtester.engine import run_all
from backtester.report import generate_report
from backtester.money_management import simulate, print_report


def get_symbols(timeframe: str) -> list[str]:
    path = DATA_DIR / timeframe
    if not path.exists():
        return []
    return [f.stem for f in path.glob("*.csv")]


def print_comparison(results: dict) -> None:
    print("\n" + "=" * 60)
    print("          COMPARISON: 5m vs 15m")
    print("=" * 60)
    print(f"{'Metric':<25} {'5m':>15} {'15m':>15}")
    print("-" * 60)

    for tf, df in results.items():
        if df.empty:
            print(f"{tf}: no signals")

    metrics = {}
    for tf, df in results.items():
        if df.empty:
            metrics[tf] = {}
            continue
        from backtester.report import win_rate, avg_pnl
        metrics[tf] = {
            "Signals":       len(df),
            "WR 1h (%)":     win_rate(df["outcome_1h"]),
            "WR 4h (%)":     win_rate(df["outcome_4h"]),
            "WR 24h (%)":    win_rate(df["outcome_24h"]),
            "Avg P&L 1h":    avg_pnl(df["outcome_1h"]),
            "Avg P&L 4h":    avg_pnl(df["outcome_4h"]),
            "LONG signals":  (df["direction"] == "LONG").sum(),
            "SHORT signals": (df["direction"] == "SHORT").sum(),
        }

    for metric in metrics.get("5m", {}).keys():
        v5  = metrics.get("5m",  {}).get(metric, "n/a")
        v15 = metrics.get("15m", {}).get(metric, "n/a")
        if isinstance(v5, float):
            print(f"{metric:<25} {v5:>15.2f} {v15:>15.2f}")
        else:
            print(f"{metric:<25} {str(v5):>15} {str(v15):>15}")

    print("=" * 60 + "\n")


async def main():
    results = {}

    for timeframe in ["5m", "15m"]:
        symbols = get_symbols(timeframe)
        if not symbols:
            logger.warning(f"No data for {timeframe}, skipping")
            continue

        logger.info(f"Running {timeframe} backtest on {len(symbols)} symbols...")
        df = run_all(symbols, timeframe)
        results[timeframe] = df

        print(f"\n{'='*60}")
        print(f"  RESULTS FOR {timeframe.upper()}")
        print(f"{'='*60}")
        generate_report(df)

        mm_report = simulate(df)
        print_report(mm_report)

    if len(results) == 2:
        print_comparison(results)


if __name__ == "__main__":
    asyncio.run(main())