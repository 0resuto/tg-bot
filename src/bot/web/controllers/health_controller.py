"""Controller handling health checks and diagnostic status."""

from __future__ import annotations

from aiohttp import web

from bot.web.dependencies import WebContainer


async def handle_get_health(request: web.Request) -> web.Response:
    """GET /api/checklist - Run live health checks against all production services."""
    container: WebContainer = request.app["container"]
    result = await container.health_service.check_all()
    return web.json_response(result)
