"""Controller for inspecting the Redis sliding conversation window."""

from __future__ import annotations

from aiohttp import web

from bot.web.dependencies import WebContainer
from bot.web.services.simulator_service import SIMULATOR_CHAT_ID


async def handle_get_context(request: web.Request) -> web.Response:
    """GET /api/context?chat_id=... - Return current sliding context buffer."""
    container: WebContainer = request.app["container"]
    chat_id_param = request.query.get("chat_id")
    chat_id = (
        int(chat_id_param)
        if chat_id_param and chat_id_param.lstrip("-").isdigit()
        else SIMULATOR_CHAT_ID
    )

    if not container.context_builder:
        return web.json_response({"messages": []})

    try:
        messages = await container.context_builder.get_context(chat_id)
        return web.json_response(
            {
                "messages": [
                    {
                        "message_id": m.message_id,
                        "user_id": m.user_id,
                        "display_name": m.display_name,
                        "text": m.text,
                        "timestamp": m.timestamp.isoformat(),
                    }
                    for m in messages
                ]
            }
        )
    except Exception:
        return web.json_response({"messages": []})
