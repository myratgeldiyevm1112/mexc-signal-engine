import pandas as pd
import pandas_ta as ta


def calculate_rsi(closes: list[float], period: int = 14) -> float | None:
    """
    Calculate RSI using Wilder's smoothing method.
    Returns the last RSI value, or None if not enough data.
    """
    if len(closes) < period + 1:
        return None

    series = pd.Series(closes)
    rsi = ta.rsi(series, length=period)

    if rsi is None or rsi.empty:
        return None

    last = rsi.iloc[-1]
    return float(last) if pd.notna(last) else None
