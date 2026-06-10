from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Redis
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str = ""

    # PostgreSQL
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    postgres_db: str = "mexc_signals"
    postgres_user: str = "postgres"
    postgres_password: str

    # MinIO
    minio_host: str = "minio"
    minio_port: int = 9000
    minio_access_key: str
    minio_secret_key: str
    minio_bucket_charts: str = "charts"
    minio_secure: bool = False

    # MEXC
    mexc_api_key: str = ""
    mexc_api_secret: str = ""
    mexc_rest_url: str = "https://api.mexc.com"
    mexc_ws_url: str = "wss://wbs.mexc.com/ws"
    mexc_symbols_per_ws_connection: int = 100

    # Telegram
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # Strategy
    filter_price_change_percent: float = 8.0
    filter_rsi_overbought: float = 80.0
    filter_rsi_oversold: float = 20.0
    filter_rsi_period: int = 14
    signal_cooldown_minutes: int = 240

    # Candle buffers
    candles_5min_buffer: int = 200
    candles_15min_buffer: int = 200
    candles_1h_buffer: int = 50
    chart_hours: int = 12

    # Services
    collector_health_port: int = 8001
    analyzer_health_port: int = 8002
    chart_builder_health_port: int = 8003
    notifier_health_port: int = 8004

    # Environment
    env: str = "development"
    log_level: str = "INFO"
    http_proxy: str = ""


# A single instance — imported across all services
settings = Settings()