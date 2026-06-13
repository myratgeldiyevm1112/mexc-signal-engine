# MEXC Signal Engine 🚀

Automated trading signal bot for MEXC Futures. Monitors 775+ USDT perpetual contracts in real-time, detects momentum signals using price change + RSI filters, and sends alerts to Telegram with candlestick charts.

## Architecture

```
MEXC Futures API
      │
      ▼
┌─────────────┐     candles:{symbol}:{tf}     ┌──────────────┐
│  Collector  │ ────────────────────────────▶ │   Analyzer   │
│  (WS + REST)│                               │  (RSI + %)   │
└─────────────┘                               └──────┬───────┘
                                                     │ stream:signals
                                                     ▼
                                             ┌───────────────┐
                                             │ Chart Builder │
                                             │  (matplotlib) │
                                             └──────┬────────┘
                                                    │ stream:chart_ready
                                                    ▼
                                             ┌──────────────┐
                                             │   Notifier   │
                                             │  (Telegram)  │
                                             └──────────────┘
```

## Signal Logic

A signal fires when ALL three conditions are met simultaneously:

| Filter | LONG | SHORT |
|--------|------|-------|
| Price change (15m) | ≥ +8% | ≤ -8% |
| RSI 1h | > 80 | < 20 |
| RSI 15m | > 80 | < 20 |

Cooldown: 4 hours per symbol after signal.

## Services

| Service | Description | Port |
|---------|-------------|------|
| `collector` | Fetches historical klines via REST, streams live candles via WebSocket | 8001 |
| `analyzer` | Runs filters every 60s across all symbols | 8002 |
| `chart_builder` | Renders candlestick PNG chart, uploads to MinIO | 8003 |
| `notifier` | Sends chart + caption to Telegram | 8004 |

## Requirements

- Docker + Docker Compose
- Telegram bot token + chat ID
- MEXC API (public endpoints only, no API key needed for data)

## Quick Start

### 1. Clone

```bash
git clone https://github.com/yourname/mexc-signal-engine.git
cd mexc-signal-engine
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env with your values
```

Required variables in `.env`:

```env
# PostgreSQL
POSTGRES_DB=mexc_signals
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password

# MinIO
MINIO_ACCESS_KEY=your_minio_key
MINIO_SECRET_KEY=your_minio_secret

# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

### 3. Run

```bash
docker compose up -d --build
```

### 4. Check logs

```bash
docker compose logs -f analyzer        # watch signals
docker compose logs -f collector       # watch data ingestion
docker compose logs -f chart_builder   # watch chart generation
docker compose logs -f notifier        # watch telegram delivery
```

### 5. Verify data in Redis

```bash
docker exec -it mexc_redis redis-cli
> LLEN candles:BTC_USDT:5m    # should be 200
> LLEN candles:BTC_USDT:15m   # should be 200
> LLEN candles:BTC_USDT:1h    # should be 50
```

## Deploy on VPS

```bash
# On VPS
git clone https://github.com/yourname/mexc-signal-engine.git
cd mexc-signal-engine
cp .env.example .env
nano .env  # fill in real values
docker compose up -d --build
```

Collector loads history for all 775 symbols on startup (~5-10 min), then switches to WebSocket streaming.

## Run Tests

```bash
poetry install
poetry run pytest tests/ -v
```

## Configuration (`.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `FILTER_PRICE_CHANGE_PERCENT` | `8.0` | Min price change % to trigger signal |
| `FILTER_RSI_OVERBOUGHT` | `80.0` | RSI overbought threshold |
| `FILTER_RSI_OVERSOLD` | `20.0` | RSI oversold threshold |
| `FILTER_RSI_PERIOD` | `14` | RSI calculation period |
| `SIGNAL_COOLDOWN_MINUTES` | `240` | Cooldown per symbol after signal |
| `CANDLES_5MIN_BUFFER` | `200` | 5m candle buffer size (~16h) |
| `CANDLES_15MIN_BUFFER` | `200` | 15m candle buffer size (~50h) |
| `CANDLES_1H_BUFFER` | `50` | 1h candle buffer size (~50h) |
| `MEXC_SYMBOLS_PER_WS_CONNECTION` | `100` | Symbols per WebSocket connection |

## Tech Stack

- **Python 3.12** — asyncio, aiohttp, websockets
- **Redis 7** — candle buffers (lists) + streams (signals pipeline)
- **PostgreSQL 16** — signal history
- **MinIO** — chart image storage (S3-compatible)
- **pandas-ta** — RSI calculation
- **matplotlib** — chart rendering
- **aiogram** — Telegram bot
- **loguru** — structured logging
- **Docker Compose** — orchestration

---

## 👤 Author

**Muhammet Myratgeldiyev**

- GitHub: [@myratgeldiyevm1112](https://github.com/myratgeldiyevm1112)
- LinkedIn: [Muhammet Myratgeldiyev](https://www.linkedin.com/in/muhammet-myratgeldiyev-aa8736413)

---

## 📝 License

