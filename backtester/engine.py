"""
backtester/engine.py
Runs the strategy on historical data and records signals with outcomes.
"""
import pandas as pd
import pandas_ta as ta
from loguru import logger
from pathlib import Path
from dataclasses import dataclass

from backtester.data_loader import load_csv, DATA_DIR

RSI_PERIOD = 14
PRICE_CHANGE_THRESHOLD = 8.0
RSI_OVERBOUGHT = 80.0
RSI_OVERSOLD = 20.0
COOLDOWN_CANDLES = 16  # 16 x 15m = 4 hours cooldown

OUTCOME_WINDOWS = {
    "1h":  4,   # 4 x 15m candles
    "4h":  16,  # 16 x 15m candles
    "24h": 96,  # 96 x 15m candles
}


@dataclass
class SignalRecord:
    symbol: str
    direction: str
    entry_time: pd.Timestamp
    entry_price: float
    change_15m: float
    rsi_1h: float
    rsi_15m: float
    outcome_1h: float | None   # % change after 1h
    outcome_4h: float | None   # % change after 4h
    outcome_24h: float | None  # % change after 24h


def _calc_rsi(closes: pd.Series, period: int = RSI_PERIOD) -> pd.Series:
    return ta.rsi(closes, length=period)


def run_backtest(symbol: str) -> list[SignalRecord]:
    """Run strategy on one symbol. Returns list of signal records."""
    df_15m = load_csv(symbol, "15m")
    df_1h = load_csv(symbol, "1h")

    if df_15m is None or df_1h is None:
        return []
    if len(df_15m) < RSI_PERIOD + 20:
        return []

    # Calculate RSI 15m
    df_15m["rsi"] = _calc_rsi(df_15m["close"])

    # Calculate RSI 1h — merge onto 15m by nearest timestamp
    df_1h["rsi_1h"] = _calc_rsi(df_1h["close"])
    df_1h = df_1h[["timestamp", "rsi_1h"]].dropna()

    # Merge 1h RSI onto 15m dataframe (forward fill)
    df_15m = df_15m.sort_values("timestamp").reset_index(drop=True)
    df_1h = df_1h.sort_values("timestamp").reset_index(drop=True)
    df_merged = pd.merge_asof(
        df_15m,
        df_1h,
        on="timestamp",
        direction="backward",
    )

    signals = []
    last_signal_idx = -COOLDOWN_CANDLES  # allow signal from the start

    for i in range(RSI_PERIOD + 1, len(df_merged)):
        if i - last_signal_idx < COOLDOWN_CANDLES:
            continue

        row = df_merged.iloc[i]
        prev_row = df_merged.iloc[i - 1]

        rsi_15m = row["rsi"]
        rsi_1h = row["rsi_1h"]

        if pd.isna(rsi_15m) or pd.isna(rsi_1h):
            continue

        current_price = row["close"]
        prev_price = prev_row["close"]

        if prev_price == 0:
            continue

        change_15m = (current_price - prev_price) / prev_price * 100

        direction = None

        if (change_15m >= PRICE_CHANGE_THRESHOLD
                and rsi_1h > RSI_OVERBOUGHT
                and rsi_15m > RSI_OVERBOUGHT):
            direction = "LONG"

        elif (change_15m <= -PRICE_CHANGE_THRESHOLD
              and rsi_1h < RSI_OVERSOLD
              and rsi_15m < RSI_OVERSOLD):
            direction = "SHORT"

        if direction is None:
            continue

        # Calculate outcomes
        outcomes = {}
        for window_name, candles_ahead in OUTCOME_WINDOWS.items():
            future_idx = i + candles_ahead
            if future_idx < len(df_merged):
                future_price = df_merged.iloc[future_idx]["close"]
                pct = (future_price - current_price) / current_price * 100
                outcomes[window_name] = round(pct, 4) if direction == "LONG" else round(-pct, 4)
            else:
                outcomes[window_name] = None

        signals.append(SignalRecord(
            symbol=symbol,
            direction=direction,
            entry_time=pd.Timestamp(row["timestamp"], unit="ms", tz="UTC"),
            entry_price=current_price,
            change_15m=round(change_15m, 4),
            rsi_1h=round(rsi_1h, 2),
            rsi_15m=round(rsi_15m, 2),
            outcome_1h=outcomes["1h"],
            outcome_4h=outcomes["4h"],
            outcome_24h=outcomes["24h"],
        ))

        last_signal_idx = i

    return signals


def run_all(symbols: list[str]) -> pd.DataFrame:
    """Run backtest for all symbols, return combined DataFrame."""
    all_signals = []
    total = len(symbols)

    for i, symbol in enumerate(symbols):
        signals = run_backtest(symbol)
        all_signals.extend(signals)
        if (i + 1) % 50 == 0:
            logger.info(f"Progress: {i+1}/{total} symbols, {len(all_signals)} signals so far")

    logger.info(f"Backtest complete: {len(symbols)} symbols, {len(all_signals)} total signals")

    if not all_signals:
        return pd.DataFrame()

    return pd.DataFrame([vars(s) for s in all_signals])