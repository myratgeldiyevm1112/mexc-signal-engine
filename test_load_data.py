import asyncio, aiohttp, datetime

async def test():
    async with aiohttp.ClientSession() as session:
        url = "https://contract.mexc.com/api/v1/contract/kline/BTC_USDT"
        
        # Попробуем запросить данные начиная с 3 месяца назад
        start_ts = int((datetime.datetime.now(datetime.timezone.utc) - 
                       datetime.timedelta(days=90)).timestamp())
        
        async with session.get(url, params={
            "interval": "Min15",
            "start": start_ts,
        }) as resp:
            data = await resp.json()
        
        times = data["data"]["time"]
        print(f"Candles: {len(times)}")
        start = datetime.datetime.fromtimestamp(times[0], tz=datetime.timezone.utc)
        end = datetime.datetime.fromtimestamp(times[-1], tz=datetime.timezone.utc)
        print(f"Period: {start} → {end}")
        print(f"Days: {(end - start).days}")

asyncio.run(test())