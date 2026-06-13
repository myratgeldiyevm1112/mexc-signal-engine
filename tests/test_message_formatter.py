from services.notifier.message_formatter import format_signal_message, _fmt_price


def test_long_signal_contains_rocket():
    msg = format_signal_message("BTC_USDT", "LONG", 63000.0, 8.5, 82.0, 81.0)
    assert "🚀" in msg
    assert "LONG" in msg
    assert "BTC_USDT" in msg


def test_short_signal_contains_arrow():
    msg = format_signal_message("ETH_USDT", "SHORT", 1500.0, -9.0, 18.0, 17.0)
    assert "🔻" in msg
    assert "SHORT" in msg


def test_mexc_futures_url():
    msg = format_signal_message("BTC_USDT", "LONG", 63000.0, 8.5, 82.0, 81.0)
    assert "futures.mexc.com/exchange/BTC_USDT" in msg


def test_fmt_price_large():
    assert _fmt_price(63000.0) == "63000.00"


def test_fmt_price_small():
    result = _fmt_price(0.000012)
    assert "0.0000" in result


def test_fmt_price_zero():
    assert _fmt_price(0.0) == "0"