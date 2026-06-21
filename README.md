# MEXC Signal Engine 🚀

> Real-time algorithmic trading signal bot for MEXC Futures. Monitors 775+ USDT perpetual contracts, detects high-momentum signals using multi-timeframe RSI analysis, and delivers Telegram alerts with candlestick charts.

[![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python)](https://python.org)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker)](https://docker.com)
[![Redis](https://img.shields.io/badge/Redis-7-DC382D?logo=redis)](https://redis.io)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791?logo=postgresql)](https://postgresql.org)

---

## Overview

MEXC Signal Engine is a production-grade microservices system that:

- Streams live candle data for **775+ futures pairs** via WebSocket
- Detects signals using **3-filter strategy**: price momentum + dual RSI overbought/oversold
- Analyzes **RSI divergence** (swing-based, professional method) as additional context
- Renders **candlestick charts** with RSI panel and rolling volume average
- Delivers **Telegram alerts** with chart image and signal metadata
- Provides a **web dashboard** with signal history, charts by hour, and service health
- Monitors **service health** and sends Telegram alerts on failure
- Includes a full **backtesting engine** (signal quality + money management simulation)

---

## Architecture

```
MEXC Futures API (WebSocket + REST)
           │
           ▼
   ┌───────────────┐
   │   Collector   │  Loads 90d history on startup, then streams live candles
   │  (WS + REST)  │  via 8 parallel WebSocket connections (100 symbols each)
   └───────┬───────┘
           │  Redis Lists: candles:{symbol}:{5m|15m|1h}
           ▼
   ┌───────────────┐
   │    Analyzer   │  Runs every 60s across all 775 symbols
   │  (RSI + %)    │  Detects signals + RSI divergence (swing highs/lows)
   └───────┬───────┘
           │  Redis Stream: stream:signals
           ▼
   ┌───────────────┐
   │ Chart Builder │  Renders candlestick PNG (12h, 5m candles)
   │ (matplotlib)  │  RSI panel + rolling top-5 volume avg line
   └───────┬───────┘
           │  MinIO (S3) + Redis Stream: stream:chart_ready
           ▼
   ┌───────────────┐
   │   Notifier    │  Sends photo + caption to Telegram channel
   │  (aiogram)    │  Updates PostgreSQL: telegram_sent = TRUE
   └───────────────┘

   ┌───────────────┐   ┌───────────────┐   ┌───────────────┐
   │   Watchdog    │   │   Dashboard   │   │  Backtester   │
   │ Health alerts │   │ FastAPI + JS  │   │ 90d analysis  │
   │  → Telegram   │   │  port :8005   │   │ CSV reports   │
   └───────────────┘   └───────────────┘   └───────────────┘
```

---

## Signal Strategy

A signal is generated when **all three conditions** are satisfied simultaneously:

| Filter | LONG Signal | SHORT Signal |
|--------|-------------|--------------|
| **Price change (15m)** | ≥ +8% | ≤ -8% |
| **RSI 1h** | > 80 (overbought) | < 20 (oversold) |
| **RSI 15m** | > 80 (overbought) | < 20 (oversold) |

**Cooldown**: 4 hours per symbol after a signal fires.

**RSI Divergence** (informational, does not block signals):
- Detected using real swing highs/lows over the last 60 candles
- Bullish: price lower low + RSI higher low → momentum shifting up
- Bearish: price higher high + RSI lower high → momentum weakening
- Strength reported as % difference between RSI at swing points

---

## Backtest Results

Strategy tested on **90 days** of historical data across **771 symbols** (610 signals total):

| Window | Win Rate | Avg P&L |
|--------|----------|---------|
| 1h | 54.8% | +2.43% |
| 4h | 49.6% | +2.67% |
| 24h | 36.0% | -0.26% |

**Key findings:**
- SHORT signals significantly outperform LONG (WR 4h: 53.5% vs 48.8%, Avg P&L: +4.67% vs +2.28%)
- Optimal exit window: **1h for LONG**, **4h for SHORT**
- Strategy degrades beyond 24h horizon

---

## Services

| Service | Description | Port |
|---------|-------------|------|
| `collector` | Historical data loader + WebSocket stream manager | 8001 |
| `analyzer` | Signal detection engine (RSI + price change + divergence) | 8002 |
| `chart_builder` | Candlestick chart renderer + MinIO uploader | 8003 |
| `notifier` | Telegram bot sender | 8004 |
| `dashboard` | Web UI — signal history, charts, service status | 8005 |
| `watchdog` | Health monitor — Telegram alerts on service failure | — |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.12 (asyncio) |
| Data streaming | aiohttp, websockets |
| Signal processing | pandas, pandas-ta |
| Chart rendering | matplotlib |
| Telegram bot | aiogram |
| Web dashboard | FastAPI, uvicorn, Chart.js |
| Cache / Streams | Redis 7 (Lists + Streams) |
| Database | PostgreSQL 16 (asyncpg) |
| Object storage | MinIO (S3-compatible) |
| Logging | loguru |
| Config | Pydantic Settings |
| Orchestration | Docker Compose |
| Testing | pytest, pytest-asyncio |

---

## Quick Start

### Prerequisites

- Docker + Docker Compose
- Telegram bot token ([create via @BotFather](https://t.me/BotFather))
- Telegram chat/channel ID

### 1. Clone

```bash
git clone https://github.com/myratgeldiyevm1112/mexc-signal-engine.git
cd mexc-signal-engine
```

### 2. Configure

```bash
cp .env.example .env
nano .env
```

Minimum required variables:

```env
POSTGRES_PASSWORD=your_secure_password
MINIO_ACCESS_KEY=your_minio_key
MINIO_SECRET_KEY=your_minio_secret
TELEGRAM_BOT_TOKEN=123456789:AABBCCDDEEFFaabbccddeeff
TELEGRAM_CHAT_ID=-1001234567890
```

### 3. Start

```bash
docker compose up -d --build
```

### 4. Initialize database

```bash
docker exec -it mexc_postgres psql -U postgres -d mexc_signals -c "
CREATE TABLE IF NOT EXISTS signals (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(50) NOT NULL,
    direction VARCHAR(10) NOT NULL,
    price NUMERIC NOT NULL,
    change_15m NUMERIC NOT NULL,
    rsi_1h NUMERIC NOT NULL,
    rsi_15m NUMERIC NOT NULL,
    telegram_sent BOOLEAN DEFAULT FALSE,
    telegram_msg_id BIGINT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_signals_created_at ON signals(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_signals_symbol ON signals(symbol);
"
```

### 5. Monitor

```bash
# Watch signals being detected
docker compose logs -f analyzer

# Watch Telegram delivery
docker compose logs -f notifier

# Open web dashboard
open http://localhost:8005
```

Collector loads ~90 days of historical data for all 775 symbols on startup (~5–10 min), then switches to live WebSocket streaming.

---

## Configuration

All settings via `.env` file:

| Variable | Default | Description |
|----------|---------|-------------|
| `FILTER_PRICE_CHANGE_PERCENT` | `8.0` | Min 15m price change % to trigger signal |
| `FILTER_RSI_OVERBOUGHT` | `80.0` | RSI overbought threshold (LONG) |
| `FILTER_RSI_OVERSOLD` | `20.0` | RSI oversold threshold (SHORT) |
| `FILTER_RSI_PERIOD` | `14` | RSI lookback period (Wilder's smoothing) |
| `SIGNAL_COOLDOWN_MINUTES` | `240` | Cooldown per symbol after signal (4h) |
| `CANDLES_5MIN_BUFFER` | `200` | 5m candle buffer depth (~16h) |
| `CANDLES_15MIN_BUFFER` | `200` | 15m candle buffer depth (~50h) |
| `CANDLES_1H_BUFFER` | `50` | 1h candle buffer depth (~50h) |
| `MEXC_SYMBOLS_PER_WS_CONNECTION` | `100` | Symbols per WebSocket connection |

---

## Backtesting

```bash
# Download 90 days of historical data (15m + 1h + 5m)
python -m backtester.data_loader

# Run full backtest: signal quality + money management simulation
python -m backtester.run
```

Results saved to:
- `backtester/results.csv` — all signals with outcomes
- `backtester/mm_results.csv` — trade-by-trade P&L

---

## Testing

```bash
poetry install
poetry run pytest tests/ -v
```

Tests cover: RSI calculator, signal filters, message formatter.

---

## Verify Redis data

```bash
docker exec -it mexc_redis redis-cli
> LLEN candles:BTC_USDT:5m    # → 200
> LLEN candles:BTC_USDT:15m   # → 200
> LLEN candles:BTC_USDT:1h    # → 50
> KEYS ready:* | wc -l        # → 775
```

---

## Dashboard

Open `http://<server-ip>:8005` to view:

- Real-time signal table with filters (direction, symbol, date range)
- Signals by hour chart (identify best trading hours)
- Top symbols by signal count
- Live service health status
- Redis data summary (candle buffer sizes, symbol count)

---

## Author

**Muhammet Myratgeldiyev**

- GitHub: [@myratgeldiyevm1112](https://github.com/myratgeldiyevm1112)
- LinkedIn: [Muhammet Myratgeldiyev](https://www.linkedin.com/in/muhammet-myratgeldiyev-aa8736413)

---

## License

MIT