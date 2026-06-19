import asyncio
import json
from services.chart_builder.chart_renderer import render_chart
from shared.redis_client import get_redis_client
from shared.constants import CANDLES_KEY, TF_5M

async def main():
    redis = get_redis_client()
    key = CANDLES_KEY.format(symbol="BTC_USDT", timeframe=TF_5M)
    raw = await redis.lrange(key, 0, -1)
    candles = [json.loads(c) for c in raw]
    print(f"Got {len(candles)} candles")
    
    png = render_chart(
        symbol="BTC_USDT",
        candles_5m=candles,
        current_price=candles[-1]["close"],
        direction="LONG",
        change_15m=9.5,
        rsi_1h=82.0,
        rsi_15m=81.0,
    )
    
    with open("test_chart.png", "wb") as f:
        f.write(png)
    print(f"Chart saved: {len(png)} bytes → test_chart.png")
    await redis.aclose()

asyncio.run(main())
