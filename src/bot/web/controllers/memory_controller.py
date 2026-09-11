"""Controller for querying memory facts and executing forget operations."""

from __future__ import annotations

from aiohttp import web

from bot.web.dependencies import WebContainer
from bot.web.services.simulator_service import SIMULATOR_CHAT_ID


async def handle_get_memories(request: web.Request) -> web.Response:
    """GET /api/memories?chat_id=... - Return recent extracted facts."""
    container: WebContainer = request.app["container"]
    chat_id_param = request.query.get("chat_id")
    chat_id = int(chat_id_param) if chat_id_param and chat_id_param.lstrip("-").isdigit() else None

    if not container.memory_query_service:
        return web.json_response({"facts": []})

    facts = await container.memory_query_service.get_memories(chat_id)
    return web.json_response({"facts": facts})


async def handle_post_forget(request: web.Request) -> web.Response:
    """POST /api/forget - Erase facts matching description."""
    container: WebContainer = request.app["container"]
    if not container.memory_query_service:
        return web.json_response(
            {"deleted_count": 0, "error": "Memory service offline"}, status=400
        )

    try:
        data = await request.json()
        description = data.get("description", "").strip()
        chat_id = data.get("chat_id", SIMULATOR_CHAT_ID)
        deleted = await container.memory_query_service.forget_fact(description, int(chat_id))
        return web.json_response({"deleted_count": deleted})
    except Exception as exc:
        return web.json_response({"deleted_count": 0, "error": str(exc)}, status=500)
