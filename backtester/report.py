"""
backtester/report.py
Generates backtest report from signals DataFrame.
"""
import pandas as pd
from pathlib import Path
from loguru import logger


def win_rate(outcomes: pd.Series) -> float:
    """% of outcomes > 0 (profitable signals)."""
    valid = outcomes.dropna()
    if len(valid) == 0:
        return 0.0
    return round((valid > 0).sum() / len(valid) * 100, 2)


def avg_pnl(outcomes: pd.Series) -> float:
    return round(outcomes.dropna().mean(), 4)


def max_losing_streak(outcomes: pd.Series) -> int:
    streak = 0
    max_streak = 0
    for v in outcomes.dropna():
        if v <= 0:
            streak += 1
            max_streak = max(max_streak, streak)
        else:
            streak = 0
    return max_streak


def generate_report(df: pd.DataFrame) -> None:
    if df.empty:
        logger.warning("No signals found — nothing to report.")
        return

    print("\n" + "=" * 60)
    print("           BACKTEST REPORT — MEXC Signal Engine")
    print("=" * 60)

    print(f"\n📊 Total signals : {len(df)}")
    print(f"   LONG          : {(df['direction'] == 'LONG').sum()}")
    print(f"   SHORT         : {(df['direction'] == 'SHORT').sum()}")
    print(f"   Symbols       : {df['symbol'].nunique()}")

    if not df["entry_time"].isna().all():
        print(f"   Period        : {df['entry_time'].min()} → {df['entry_time'].max()}")

    print("\n" + "-" * 60)
    print(f"{'Window':<10} {'Win Rate':>10} {'Avg P&L':>10} {'Max Lose Streak':>16}")
    print("-" * 60)

    for window in ["outcome_1h", "outcome_4h", "outcome_24h"]:
        label = window.replace("outcome_", "")
        wr = win_rate(df[window])
        ap = avg_pnl(df[window])
        mls = max_losing_streak(df[window])
        print(f"{label:<10} {wr:>9.1f}% {ap:>+10.2f}% {mls:>16}")

    print("\n" + "-" * 60)
    print("Top 10 symbols by signal count:")
    top = df["symbol"].value_counts().head(10)
    for sym, count in top.items():
        wr_4h = win_rate(df[df["symbol"] == sym]["outcome_4h"])
        print(f"  {sym:<20} {count:>4} signals   WR(4h): {wr_4h:.1f}%")

    print("\n" + "-" * 60)
    print("By direction:")
    for direction in ["LONG", "SHORT"]:
        sub = df[df["direction"] == direction]
        if sub.empty:
            continue
        print(f"\n  {direction}:")
        for window in ["outcome_1h", "outcome_4h", "outcome_24h"]:
            label = window.replace("outcome_", "")
            print(f"    {label}: WR={win_rate(sub[window]):.1f}%  Avg={avg_pnl(sub[window]):+.2f}%")

    print("\n" + "=" * 60)

    # Save to CSV
    out_path = Path("backtester/results.csv")
    df.to_csv(out_path, index=False)
    print(f"\n💾 Full results saved to {out_path}")
    print("=" * 60 + "\n")