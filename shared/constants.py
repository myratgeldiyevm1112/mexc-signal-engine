# Redis keys for candles
# Used: candles:BTCUSDT:5m, candles:BTCUSDT:15m, candles:BTCUSDT:1h
CANDLES_KEY = "candles:{symbol}:{timeframe}"

# Flag indicating if the symbol is ready (historical data loaded)
READY_KEY = "ready:{symbol}"

# Cooldown after signal for each symbol
COOLDOWN_KEY = "cooldown:{symbol}"

# Bot start time (Unix timestamp)
BOT_START_TIME_KEY = "bot_start_time"

# Redis Streams — channels between services
STREAM_TICK_UPDATES = "stream:tick_updates"    # collector → analyzer
STREAM_SIGNALS = "stream:signals"              # analyzer → chart_builder
STREAM_CHART_READY = "stream:chart_ready"      # chart_builder → notifier

# Timeframes for candles
TF_5M = "5m"
TF_15M = "15m"
TF_1H = "1h"

MEXC_INTERVAL_MAP = {
    TF_5M:  "5m",
    TF_15M: "15m",
    TF_1H:  "60m",
}