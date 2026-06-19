from datetime import datetime, timezone


def format_signal_message(
    symbol: str,
    direction: str,
    price: float,
    change_15m: float,
    rsi_1h: float,
    rsi_15m: float,
    divergence_kind: str = "",
    divergence_strength: float = 0.0,
    divergence_desc: str = "",
) -> str:
    emoji = "🚀" if direction == "LONG" else "🔻"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    mexc_url = f"https://futures.mexc.com/exchange/{symbol}"

    # Divergence line
    if divergence_kind == "bullish":
        div_line = f"\n⚡ Дивергенция    : <b>Бычья +{divergence_strength:.1f}%</b> 📈"
    elif divergence_kind == "bearish":
        div_line = f"\n⚡ Дивергенция    : <b>Медвежья -{divergence_strength:.1f}%</b> 📉"
    else:
        div_line = ""

    return (
        f"{emoji} <b>{direction} SIGNAL — {symbol}</b>\n\n"
        f"📊 Изменение 15m : <b>{change_15m:+.2f}%</b>\n"
        f"📈 RSI 1h        : <b>{rsi_1h:.1f}</b>\n"
        f"📈 RSI 15m       : <b>{rsi_15m:.1f}</b>"
        f"{div_line}\n\n"
        f"💰 Цена          : <code>{_fmt_price(price)}</code> USDT\n"
        f"📅 Время         : {now}\n\n"
        f'🔗 <a href="{mexc_url}">Открыть пару на MEXC Futures</a>'
    )

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