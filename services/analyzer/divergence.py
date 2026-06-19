"""
services/analyzer/divergence.py
Professional RSI divergence detector using swing highs/lows.

Rules:
  - Find real swing highs/lows (local extrema) in price
  - Compare with RSI at the same swing points
  - Bullish divergence:  price lower low + RSI higher low  (RSI zone < 50)
  - Bearish divergence:  price higher high + RSI lower high (RSI zone > 50)
  - Strength = % difference between RSI values at the two swings
"""
from dataclasses import dataclass
import numpy as np
import pandas as pd
import pandas_ta as ta


# ── Configuration ─────────────────────────────────────────
SWING_LOOKBACK   = 5    # candles on each side to confirm a swing point
DIVERGENCE_WINDOW = 60  # how many candles back to search for swings
MIN_SWING_GAP    = 5    # minimum candles between two swings
RSI_PERIOD       = 14
MIN_STRENGTH     = 3.0  # minimum RSI % difference to count as divergence
# ──────────────────────────────────────────────────────────


@dataclass
class DivergenceResult:
    detected: bool
    kind: str | None        # "bullish", "bearish", or None
    strength: float         # RSI % difference between swings (positive = strong)
    rsi_swing1: float | None
    rsi_swing2: float | None
    price_swing1: float | None
    price_swing2: float | None
    description: str        # human-readable


def _find_swing_highs(prices: np.ndarray, lookback: int) -> list[int]:
    """Find indices of swing highs (local maxima)."""
    highs = []
    for i in range(lookback, len(prices) - lookback):
        window = prices[i - lookback: i + lookback + 1]
        if prices[i] == np.max(window):
            highs.append(i)
    return highs


def _find_swing_lows(prices: np.ndarray, lookback: int) -> list[int]:
    """Find indices of swing lows (local minima)."""
    lows = []
    for i in range(lookback, len(prices) - lookback):
        window = prices[i - lookback: i + lookback + 1]
        if prices[i] == np.min(window):
            lows.append(i)
    return lows


def _filter_swings(swings: list[int], min_gap: int) -> list[int]:
    """Remove swings that are too close to each other."""
    if not swings:
        return []
    filtered = [swings[0]]
    for s in swings[1:]:
        if s - filtered[-1] >= min_gap:
            filtered.append(s)
    return filtered


def detect_divergence(
    closes: list[float],
    rsi_period: int = RSI_PERIOD,
    swing_lookback: int = SWING_LOOKBACK,
    window: int = DIVERGENCE_WINDOW,
    min_gap: int = MIN_SWING_GAP,
    min_strength: float = MIN_STRENGTH,
) -> DivergenceResult:
    """
    Detect RSI divergence on the last `window` candles.

    Returns DivergenceResult with type and strength.
    """
    no_divergence = DivergenceResult(
        detected=False,
        kind=None,
        strength=0.0,
        rsi_swing1=None,
        rsi_swing2=None,
        price_swing1=None,
        price_swing2=None,
        description="No divergence",
    )

    if len(closes) < rsi_period + window + swing_lookback:
        return no_divergence

    # Use last `window` candles for divergence search
    prices = np.array(closes[-window:], dtype=float)

    # Calculate RSI for the full series (for accuracy), then slice
    series = pd.Series(closes, dtype=float)
    rsi_full = ta.rsi(series, length=rsi_period)
    if rsi_full is None or rsi_full.isna().all():
        return no_divergence

    rsi_arr = rsi_full.to_numpy()[-window:]

    if len(rsi_arr) != len(prices):
        return no_divergence

    current_rsi = rsi_arr[-1]
    if np.isnan(current_rsi):
        return no_divergence

    # ── Check BEARISH divergence (using swing highs) ──────
    # Valid when RSI > 50 (momentum zone)
    if current_rsi > 50:
        swing_highs = _find_swing_highs(prices, swing_lookback)
        swing_highs = _filter_swings(swing_highs, min_gap)

        # Need at least 2 swing highs
        if len(swing_highs) >= 2:
            # Take the last two swing highs
            idx1, idx2 = swing_highs[-2], swing_highs[-1]

            price1, price2 = prices[idx1], prices[idx2]
            rsi1, rsi2 = rsi_arr[idx1], rsi_arr[idx2]

            if np.isnan(rsi1) or np.isnan(rsi2):
                pass
            elif price2 > price1 and rsi2 < rsi1:
                # Price: higher high, RSI: lower high → bearish divergence
                strength = abs((rsi1 - rsi2) / rsi1 * 100)
                if strength >= min_strength:
                    label = _strength_label(strength)
                    return DivergenceResult(
                        detected=True,
                        kind="bearish",
                        strength=round(strength, 2),
                        rsi_swing1=round(rsi1, 2),
                        rsi_swing2=round(rsi2, 2),
                        price_swing1=round(price1, 8),
                        price_swing2=round(price2, 8),
                        description=f"Медвежья дивергенция ({label}) -{strength:.1f}%",
                    )

    # ── Check BULLISH divergence (using swing lows) ───────
    # Valid when RSI < 50 (weakness zone)
    if current_rsi < 50:
        swing_lows = _find_swing_lows(prices, swing_lookback)
        swing_lows = _filter_swings(swing_lows, min_gap)

        if len(swing_lows) >= 2:
            idx1, idx2 = swing_lows[-2], swing_lows[-1]

            price1, price2 = prices[idx1], prices[idx2]
            rsi1, rsi2 = rsi_arr[idx1], rsi_arr[idx2]

            if np.isnan(rsi1) or np.isnan(rsi2):
                pass
            elif price2 < price1 and rsi2 > rsi1:
                # Price: lower low, RSI: higher low → bullish divergence
                strength = abs((rsi2 - rsi1) / rsi1 * 100)
                if strength >= min_strength:
                    label = _strength_label(strength)
                    return DivergenceResult(
                        detected=True,
                        kind="bullish",
                        strength=round(strength, 2),
                        rsi_swing1=round(rsi1, 2),
                        rsi_swing2=round(rsi2, 2),
                        price_swing1=round(price1, 8),
                        price_swing2=round(price2, 8),
                        description=f"Бычья дивергенция ({label}) +{strength:.1f}%",
                    )

    return no_divergence


def _strength_label(strength: float) -> str:
    if strength >= 20:
        return "очень сильная"
    if strength >= 10:
        return "сильная"
    if strength >= 5:
        return "средняя"
    return "слабая"