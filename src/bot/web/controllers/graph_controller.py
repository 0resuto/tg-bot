"""Controller for querying interactive knowledge graph data."""

from __future__ import annotations

from aiohttp import web

from bot.web.dependencies import WebContainer


async def handle_get_graph(request: web.Request) -> web.Response:
    """GET /api/graph?chat_id=... - Return nodes and edges for Vis.js visualization."""
    container: WebContainer = request.app["container"]
    chat_id_param = request.query.get("chat_id")
    chat_id = int(chat_id_param) if chat_id_param and chat_id_param.lstrip("-").isdigit() else None

    result = await container.graph_service.get_graph(chat_id)
    return web.json_response(result)
