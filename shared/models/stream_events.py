from pydantic import BaseModel
from shared.models.signal import SignalDirection


class SignalEvent(BaseModel):
    """Trading event in stream:signals (analyzer → chart_builder)."""
    signal_id: int
    symbol: str
    direction: SignalDirection
    price: float
    change_15m: float
    rsi_1h: float
    rsi_15m: float


class ChartReadyEvent(BaseModel):
    """Trading event in stream:chart_ready (chart_builder → notifier)."""
    signal_id: int
    symbol: str
    direction: SignalDirection
    price: float
    change_15m: float
    rsi_1h: float
    rsi_15m: float
    chart_url: str