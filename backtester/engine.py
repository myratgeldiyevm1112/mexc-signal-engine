"""
backtester/engine.py
Runs the strategy on historical data and records signals with outcomes.
Supports 5m and 15m timeframes.
"""
import pandas as pd
import pandas_ta as ta
from loguru import logger
from dataclasses import dataclass

from backtester.data_loader import load_csv

RSI_PERIOD = 14
PRICE_CHANGE_THRESHOLD = 8.0
RSI_OVERBOUGHT = 80.0
RSI_OVERSOLD = 20.0

# Timeframe configs: (primary_tf, higher_tf, cooldown_candles, outcome_windows)
TF_CONFIG = {
    "5m": {
        "primary":  "5m",
        "higher":   "1h",
        "cooldown": 48,   # 48 x 5m = 4 hours
        "outcomes": {
            "1h":  12,    # 12 x 5m = 1h
            "4h":  48,    # 48 x 5m = 4h
            "24h": 288,   # 288 x 5m = 24h
        },
    },
    "15m": {
        "primary":  "15m",
        "higher":   "1h",
        "cooldown": 16,   # 16 x 15m = 4 hours
        "outcomes": {
            "1h":  4,     # 4 x 15m = 1h
            "4h":  16,    # 16 x 15m = 4h
            "24h": 96,    # 96 x 15m = 24h
        },
    },
}


@dataclass
class SignalRecord:
    symbol: str
    direction: str
    timeframe: str
    entry_time: pd.Timestamp
    entry_price: float
    change_pct: float
    rsi_high: float   # RSI on higher timeframe (1h)
    rsi_primary: float  # RSI on primary timeframe
    outcome_1h: float | None
    outcome_4h: float | None
    outcome_24h: float | None


def _calc_rsi(closes: pd.Series, period: int = RSI_PERIOD) -> pd.Series:
    return ta.rsi(closes, length=period)


def run_backtest(symbol: str, timeframe: str = "15m") -> list[SignalRecord]:
    """Run strategy on one symbol for given timeframe."""
    cfg = TF_CONFIG[timeframe]
    primary_tf = cfg["primary"]
    higher_tf = cfg["higher"]
    cooldown = cfg["cooldown"]
    outcomes = cfg["outcomes"]

    df_primary = load_csv(symbol, primary_tf)
    df_higher = load_csv(symbol, higher_tf)

    if df_primary is None or df_higher is None:
        return []
    if len(df_primary) < RSI_PERIOD + 20:
        return []

    # Calculate RSI on primary timeframe
    df_primary["rsi"] = _calc_rsi(df_primary["close"])

    # Calculate RSI on higher timeframe
    df_higher["rsi_high"] = _calc_rsi(df_higher["close"])
    df_higher = df_higher[["timestamp", "rsi_high"]].dropna()

    # Merge higher TF RSI onto primary
    df_primary = df_primary.sort_values("timestamp").reset_index(drop=True)
    df_higher = df_higher.sort_values("timestamp").reset_index(drop=True)
    df_merged = pd.merge_asof(
        df_primary,
        df_higher,
        on="timestamp",
        direction="backward",
    )

    signals = []
    last_signal_idx = -cooldown

    for i in range(RSI_PERIOD + 1, len(df_merged)):
        if i - last_signal_idx < cooldown:
            continue

        row = df_merged.iloc[i]
        prev_row = df_merged.iloc[i - 1]

        rsi_primary = row["rsi"]
        rsi_high = row["rsi_high"]

        if pd.isna(rsi_primary) or pd.isna(rsi_high):
            continue

        current_price = row["close"]
        prev_price = prev_row["close"]

        if prev_price == 0:
            continue

        change_pct = (current_price - prev_price) / prev_price * 100
        direction = None

        if (change_pct >= PRICE_CHANGE_THRESHOLD
                and rsi_high > RSI_OVERBOUGHT
                and rsi_primary > RSI_OVERBOUGHT):
            direction = "LONG"

        elif (change_pct <= -PRICE_CHANGE_THRESHOLD
              and rsi_high < RSI_OVERSOLD
              and rsi_primary < RSI_OVERSOLD):
            direction = "SHORT"

        if direction is None:
            continue

        # Calculate outcomes
        signal_outcomes = {}
        for window_name, candles_ahead in outcomes.items():
            future_idx = i + candles_ahead
            if future_idx < len(df_merged):
                future_price = df_merged.iloc[future_idx]["close"]
                pct = (future_price - current_price) / current_price * 100
                signal_outcomes[window_name] = round(pct, 4) if direction == "LONG" else round(-pct, 4)
            else:
                signal_outcomes[window_name] = None

        signals.append(SignalRecord(
            symbol=symbol,
            direction=direction,
            timeframe=timeframe,
            entry_time=pd.Timestamp(row["timestamp"], unit="ms", tz="UTC"),
            entry_price=current_price,
            change_pct=round(change_pct, 4),
            rsi_high=round(rsi_high, 2),
            rsi_primary=round(rsi_primary, 2),
            outcome_1h=signal_outcomes["1h"],
            outcome_4h=signal_outcomes["4h"],
            outcome_24h=signal_outcomes["24h"],
        ))

        last_signal_idx = i

    return signals


def run_all(symbols: list[str], timeframe: str = "15m") -> pd.DataFrame:
    """Run backtest for all symbols, return combined DataFrame."""
    all_signals = []
    total = len(symbols)

    for i, symbol in enumerate(symbols):
        signals = run_backtest(symbol, timeframe)
        all_signals.extend(signals)
        if (i + 1) % 50 == 0:
            logger.info(f"[{timeframe}] Progress: {i+1}/{total} symbols, {len(all_signals)} signals so far")

    logger.info(f"[{timeframe}] Backtest complete: {len(symbols)} symbols, {len(all_signals)} total signals")

    if not all_signals:
        return pd.DataFrame()

    return pd.DataFrame([vars(s) for s in all_signals])