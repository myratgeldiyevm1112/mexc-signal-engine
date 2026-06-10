from pydantic import BaseModel


class Candle(BaseModel):
    """One OHLCV candle."""
    symbol: str
    timeframe: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    timestamp: int  # Unix timestamp in milliseconds (candle opening time)