"""
services/dashboard/main.py
FastAPI web dashboard for MEXC Signal Engine.
"""
import asyncio
from datetime import datetime, timezone, timedelta

import httpx
from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse
import asyncpg
import redis.asyncio as aioredis

from shared.config import settings
from shared.postgres_client import get_postgres_pool
from shared.redis_client import get_redis_client
from services.dashboard.templates import render_page

app = FastAPI(title="MEXC Signal Dashboard")

# Global connections
_pool: asyncpg.Pool | None = None
_redis: aioredis.Redis | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await get_postgres_pool()
    return _pool


def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = get_redis_client()
    return _redis


HEALTH_URLS = {
    "collector":     f"http://collector:{settings.collector_health_port}/health",
    "analyzer":      f"http://analyzer:{settings.analyzer_health_port}/health",
    "chart_builder": f"http://chart_builder:{settings.chart_builder_health_port}/health",
    "notifier":      f"http://notifier:{settings.notifier_health_port}/health",
}


async def check_services() -> dict:
    statuses = {}
    async with httpx.AsyncClient(timeout=3.0) as client:
        for name, url in HEALTH_URLS.items():
            try:
                resp = await client.get(url)
                statuses[name] = "healthy" if resp.status_code == 200 else "unhealthy"
            except Exception:
                statuses[name] = "down"
    return statuses


async def get_signals(
    pool: asyncpg.Pool,
    limit: int = 50,
    offset: int = 0,
    direction: str | None = None,
    symbol: str | None = None,
    days: int = 7,
) -> list[dict]:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    conditions = ["created_at >= $1"]
    params = [since]
    idx = 2

    if direction:
        conditions.append(f"direction = ${idx}")
        params.append(direction)
        idx += 1
    if symbol:
        conditions.append(f"symbol ILIKE ${idx}")
        params.append(f"%{symbol}%")
        idx += 1

    where = " AND ".join(conditions)
    params += [limit, offset]

    rows = await pool.fetch(
        f"""
        SELECT id, symbol, direction, price, change_15m, rsi_1h, rsi_15m,
               telegram_sent, created_at
        FROM signals
        WHERE {where}
        ORDER BY created_at DESC
        LIMIT ${idx} OFFSET ${idx+1}
        """,
        *params,
    )
    return [dict(r) for r in rows]


async def get_stats(pool: asyncpg.Pool, days: int = 7) -> dict:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    row = await pool.fetchrow(
        """
        SELECT
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE direction = 'LONG') as long_count,
            COUNT(*) FILTER (WHERE direction = 'SHORT') as short_count,
            COUNT(*) FILTER (WHERE telegram_sent = TRUE) as sent_count,
            AVG(ABS(change_15m)) as avg_change,
            AVG(rsi_1h) as avg_rsi_1h,
            AVG(rsi_15m) as avg_rsi_15m
        FROM signals
        WHERE created_at >= $1
        """,
        since,
    )
    return dict(row)


async def get_signals_by_hour(pool: asyncpg.Pool, days: int = 7) -> list[dict]:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = await pool.fetch(
        """
        SELECT
            EXTRACT(HOUR FROM created_at) as hour,
            COUNT(*) as count,
            COUNT(*) FILTER (WHERE direction = 'LONG') as long_count,
            COUNT(*) FILTER (WHERE direction = 'SHORT') as short_count
        FROM signals
        WHERE created_at >= $1
        GROUP BY hour
        ORDER BY hour
        """,
        since,
    )
    return [dict(r) for r in rows]


async def get_top_symbols(pool: asyncpg.Pool, days: int = 7) -> list[dict]:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = await pool.fetch(
        """
        SELECT symbol, COUNT(*) as count,
               COUNT(*) FILTER (WHERE direction = 'LONG') as long_count,
               COUNT(*) FILTER (WHERE direction = 'SHORT') as short_count,
               AVG(ABS(change_15m)) as avg_change
        FROM signals
        WHERE created_at >= $1
        GROUP BY symbol
        ORDER BY count DESC
        LIMIT 15
        """,
        since,
    )
    return [dict(r) for r in rows]


async def get_redis_stats(redis: aioredis.Redis) -> dict:
    try:
        ready_keys = await redis.keys("ready:*")
        btc_5m = await redis.llen("candles:BTC_USDT:5m")
        btc_15m = await redis.llen("candles:BTC_USDT:15m")
        btc_1h = await redis.llen("candles:BTC_USDT:1h")
        db_size = await redis.dbsize()
        return {
            "ready_symbols": len(ready_keys),
            "btc_5m": btc_5m,
            "btc_15m": btc_15m,
            "btc_1h": btc_1h,
            "db_size": db_size,
        }
    except Exception:
        return {}


@app.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    direction: str | None = Query(None),
    symbol: str | None = Query(None),
    days: int = Query(7),
    page: int = Query(1),
):
    pool = await get_pool()
    redis = get_redis()
    limit = 50
    offset = (page - 1) * limit

    signals, stats, by_hour, top_symbols, service_statuses, redis_stats = await asyncio.gather(
        get_signals(pool, limit, offset, direction, symbol, days),
        get_stats(pool, days),
        get_signals_by_hour(pool, days),
        get_top_symbols(pool, days),
        check_services(),
        get_redis_stats(redis),
    )

    html = render_page(
        signals=signals,
        stats=stats,
        by_hour=by_hour,
        top_symbols=top_symbols,
        service_statuses=service_statuses,
        redis_stats=redis_stats,
        filters={"direction": direction, "symbol": symbol, "days": days},
        page=page,
    )
    return HTMLResponse(html)


@app.get("/api/stats")
async def api_stats(days: int = 7):
    pool = await get_pool()
    stats = await get_stats(pool, days)
    return JSONResponse(stats)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "dashboard"}


def run():
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8005)


if __name__ == "__main__":
    run()