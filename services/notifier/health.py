"""
services/chart_builder/health.py
Simple HTTP /health endpoint.
"""

from aiohttp import web
from loguru import logger


async def _health(request: web.Request) -> web.Response:
    return web.json_response({"status": "ok"})


async def run_health_server(port: int) -> None:
    app = web.Application()
    app.router.add_get("/health", _health)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"Health server listening on :{port}/health")
