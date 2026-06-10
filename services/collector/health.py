from aiohttp import web
from loguru import logger


async def health_handler(request: web.Request) -> web.Response:
    return web.json_response({"status": "ok", "service": "collector"})


async def run_health_server(port: int) -> None:
    app = web.Application()
    app.router.add_get("/health", health_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"Health server started on port {port}")