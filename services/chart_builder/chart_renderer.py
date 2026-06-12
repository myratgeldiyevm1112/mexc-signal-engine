"""
services/chart_builder/chart_renderer.py
Renders candlestick 5m chart (last 12h) + volume panel with rolling top-5 avg line.
Returns PNG bytes (for MinIO upload), not a file on disk.
"""

import io
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.gridspec import GridSpec
import numpy as np
import pandas as pd
import pandas_ta as ta

logger = logging.getLogger(__name__)

CANDLES_12H = 144     # 5m * 144 = 12h
VOLUME_LOOKBACK = 200  # how many candles back for top-5 max volume avg
RSI_PERIOD = 14
RSI_OVERBOUGHT = 80
RSI_OVERSOLD = 20


def render_chart(
    symbol: str,
    candles_5m: List[Dict[str, Any]],
    current_price: float,
    direction: str,
    change_15m: float,
    rsi_1h: float,
    rsi_15m: float,
) -> bytes:
    """
    candles_5m: list of dicts with keys timestamp, open, high, low, close, volume
                (oldest -> newest order expected)
    Returns: PNG image as bytes.
    """
    if not candles_5m:
        raise ValueError("No 5m candle data")

    display = candles_5m[-CANDLES_12H:]
    n = len(display)

    opens  = np.array([c["open"]   for c in display], dtype=float)
    highs  = np.array([c["high"]   for c in display], dtype=float)
    lows   = np.array([c["low"]    for c in display], dtype=float)
    closes = np.array([c["close"]  for c in display], dtype=float)
    vols   = np.array([c["volume"] for c in display], dtype=float)

    # RSI 5m — use full available history for accurate warmup, then slice to display window
    all_closes = pd.Series([c["close"] for c in candles_5m], dtype=float)
    rsi_full = ta.rsi(all_closes, length=RSI_PERIOD)
    rsi_series = rsi_full.to_numpy()[-n:] if rsi_full is not None else np.full(n, np.nan)

    # Top-5 max volume average over last VOLUME_LOOKBACK candles (flat reference line)
    vol_lookback = np.array(
        [c["volume"] for c in candles_5m[-VOLUME_LOOKBACK:]], dtype=float
    )
    top5_avg_volume = _top5_avg_volume(vol_lookback)

    x = np.arange(n)

    # --- Palette ---
    is_long      = direction == "LONG"
    signal_color = "#00e676" if is_long else "#ff1744"
    bg_color     = "#0d0d14"
    grid_color   = "#1a1a2e"
    text_color   = "#d0d0e0"
    bull_color   = "#00e676"
    bear_color   = "#ff1744"
    vol_bull     = "#2979ff"
    vol_bear     = "#d32f2f"
    avg_color    = "#ffd740"

    plt.rcParams.update({"font.family": "monospace", "axes.unicode_minus": False})

    # --- Figure: 3 panels (candles + RSI + volume) ---
    fig = plt.figure(figsize=(14, 9), facecolor=bg_color)
    gs  = GridSpec(3, 1, figure=fig, height_ratios=[3, 1.2, 1.2], hspace=0.05)

    ax_c   = fig.add_subplot(gs[0])
    ax_rsi = fig.add_subplot(gs[1], sharex=ax_c)
    ax_vol = fig.add_subplot(gs[2], sharex=ax_c)

    for ax in (ax_c, ax_rsi, ax_vol):
        ax.set_facecolor(bg_color)
        ax.tick_params(colors=text_color, labelsize=8)
        ax.spines[:].set_color(grid_color)
        ax.grid(color=grid_color, linewidth=0.4, linestyle="--", alpha=0.7)

    # ── TOP: Candlestick ──────────────────────────────────
    w = 0.55
    for i in range(n):
        o, h, l, c = opens[i], highs[i], lows[i], closes[i]
        col = bull_color if c >= o else bear_color
        ax_c.plot([i, i], [l, h], color=col, linewidth=0.8, zorder=2)
        body_y = min(o, c)
        body_h = max(abs(c - o), (h - l) * 0.003)
        rect = mpatches.FancyBboxPatch(
            (i - w / 2, body_y), w, body_h,
            boxstyle="square,pad=0",
            facecolor=col, edgecolor=col, linewidth=0, zorder=3,
        )
        ax_c.add_patch(rect)

    ax_c.axhline(current_price, color=signal_color, linewidth=0.9,
                 linestyle="--", alpha=0.9, zorder=4)
    ax_c.text(n - 0.5, current_price, f"  {_fmt_price(current_price)}",
              color=signal_color, fontsize=7.5, va="center", zorder=5)

    label = "LONG ▲" if is_long else "SHORT ▼"
    ax_c.set_title(
        f"{symbol}  5m  ·  {label}  ·  ${_fmt_price(current_price)}  "
        f"(15m: {change_15m:+.2f}%)  ·  RSI1h={rsi_1h:.1f}  RSI15m={rsi_15m:.1f}",
        color=text_color, fontsize=12, fontweight="bold", pad=10,
    )
    ax_c.set_ylabel("Цена", color=text_color, fontsize=9)
    ax_c.tick_params(labelbottom=False)
    ax_c.set_xlim(-0.7, n - 0.3)

    # ── MIDDLE: RSI 5m ────────────────────────────────────
    last_rsi = float(rsi_series[-1]) if len(rsi_series) and not np.isnan(rsi_series[-1]) else 50.0

    ax_rsi.plot(x, rsi_series, color="#ffa726", linewidth=1.4,
                label=f"RSI 5m  {last_rsi:.1f}")

    ax_rsi.axhline(RSI_OVERBOUGHT, color=bear_color, linewidth=0.8, linestyle="--")
    ax_rsi.axhline(RSI_OVERSOLD,   color=bull_color, linewidth=0.8, linestyle="--")
    ax_rsi.axhline(50, color=grid_color, linewidth=0.5)

    ax_rsi.fill_between(x, RSI_OVERBOUGHT, 100, alpha=0.07, color=bear_color)
    ax_rsi.fill_between(x, 0, RSI_OVERSOLD, alpha=0.07, color=bull_color)

    ax_rsi.set_ylim(0, 100)
    ax_rsi.set_ylabel("RSI", color=text_color, fontsize=9)
    ax_rsi.tick_params(labelbottom=False)
    ax_rsi.legend(loc="upper left", fontsize=8, facecolor=bg_color,
                  labelcolor=text_color, edgecolor=grid_color)
    ax_rsi.text(0.995, RSI_OVERBOUGHT / 100, f" {RSI_OVERBOUGHT}",
                transform=ax_rsi.get_yaxis_transform(),
                color=bear_color, fontsize=7, va="center")
    ax_rsi.text(0.995, RSI_OVERSOLD / 100, f" {RSI_OVERSOLD}",
                transform=ax_rsi.get_yaxis_transform(),
                color=bull_color, fontsize=7, va="center")

    # ── BOTTOM: Volume ────────────────────────────────────
    vcols = [vol_bull if closes[i] >= opens[i] else vol_bear for i in range(n)]
    ax_vol.bar(x, vols, color=vcols, width=0.6, alpha=0.9, zorder=2)

    rolling_avg = np.full(n, top5_avg_volume)
    ax_vol.plot(
        x, rolling_avg,
        color=avg_color, linewidth=1.3, linestyle="-", zorder=3,
        label=f"Top-5 avg vol (200)  {_fmt_vol(top5_avg_volume)}",
    )

    ax_vol.set_ylabel("Объём", color=text_color, fontsize=9)
    ax_vol.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: _fmt_vol(v)))
    ax_vol.legend(loc="upper left", fontsize=8, facecolor=bg_color,
                  labelcolor=text_color, edgecolor=grid_color)

    x_labels, x_ticks = _make_time_labels(display, max_labels=9)
    ax_vol.set_xticks(x_ticks)
    ax_vol.set_xticklabels(x_labels, color=text_color, fontsize=7, rotation=15, ha="right")

    fig.text(0.99, 0.005, f"MEXC Signal Bot · {_now_utc()}",
             ha="right", va="bottom", color="#44445a", fontsize=7)

    fig.set_layout_engine("constrained")

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight", facecolor=bg_color)
    plt.close(fig)
    buf.seek(0)
    return buf.read()


# ============================================================
# HELPERS
# ============================================================

def _top5_avg_volume(vols: np.ndarray) -> float:
    if len(vols) == 0:
        return 0.0
    k = min(5, len(vols))
    top5 = np.partition(vols, -k)[-k:]
    return float(np.mean(top5))


def _make_time_labels(candles: List[Dict], max_labels: int = 9):
    n = len(candles)
    ticks = np.linspace(0, n - 1, min(max_labels, n), dtype=int)
    labels = []
    prev_day = None
    for i in ticks:
        ts = candles[i].get("timestamp")
        if ts is not None:
            try:
                ts = int(ts)
                if ts > 1e10:
                    ts //= 1000
                dt = datetime.fromtimestamp(ts, tz=timezone.utc)
                day_str = dt.strftime("%b %d")
                time_str = dt.strftime("%H:%M")
                if prev_day is None or day_str != prev_day:
                    labels.append(f"{day_str}\n{time_str}")
                    prev_day = day_str
                else:
                    labels.append(time_str)
            except Exception:
                labels.append(str(i))
        else:
            labels.append(str(i))
    return labels, ticks.tolist()


def _fmt_price(v: float) -> str:
    if v == 0:
        return "0"
    if v < 0.0001:
        return f"{v:.8f}".rstrip("0")
    if v < 1:
        return f"{v:.6f}".rstrip("0")
    if v < 100:
        return f"{v:.4f}"
    return f"{v:.2f}"


def _fmt_vol(v: float) -> str:
    if v >= 1_000_000:
        return f"{v/1_000_000:.1f}M"
    if v >= 1_000:
        return f"{v/1_000:.0f}K"
    return f"{v:.0f}"


def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")