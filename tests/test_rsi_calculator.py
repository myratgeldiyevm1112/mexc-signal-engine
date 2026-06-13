from services.analyzer.rsi_calculator import calculate_rsi


def test_rsi_returns_none_if_not_enough_data():
    assert calculate_rsi([1.0, 2.0, 3.0], period=14) is None


def test_rsi_returns_float_with_enough_data():
    closes = [float(i) for i in range(1, 31)]
    result = calculate_rsi(closes, period=14)
    assert result is not None
    assert 0.0 <= result <= 100.0


def test_rsi_overbought_on_rising_prices():
    closes = [float(i) for i in range(1, 51)]
    result = calculate_rsi(closes, period=14)
    assert result is not None
    assert result > 70.0


def test_rsi_oversold_on_falling_prices():
    closes = [float(50 - i) for i in range(50)]
    result = calculate_rsi(closes, period=14)
    assert result is not None
    assert result < 30.0