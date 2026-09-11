"""Controller handling interactive chat simulation requests."""

from __future__ import annotations

from aiohttp import web

from bot.web.dependencies import WebContainer
from bot.web.services.simulator_service import PRESET_USERS


async def handle_send_message(request: web.Request) -> web.Response:
    """POST /api/simulator/send_message - Process virtual message in sandbox."""
    container: WebContainer = request.app["container"]
    if not container.config.enable_simulator or not container.simulator_service:
        return web.json_response(
            {"success": False, "error": "Simulator mode is disabled in this environment"},
            status=403,
        )

    try:
        data = await request.json()
        user_id = int(data.get("user_id", 1))
        user_name = str(data.get("user_name", "Alice"))
        text = str(data.get("text", "")).strip()
        reply_to_bot = bool(data.get("reply_to_bot", False))

        if not text:
            return web.json_response(
                {"success": False, "error": "Message text cannot be empty"},
                status=400,
            )

        result = await container.simulator_service.send_simulated_message(
            user_id=user_id,
            user_name=user_name,
            text=text,
            reply_to_bot=reply_to_bot,
        )
        return web.json_response(result)
    except Exception as exc:
        return web.json_response(
            {"success": False, "error": str(exc)},
            status=500,
        )


async def handle_get_presets(request: web.Request) -> web.Response:
    """GET /api/simulator/presets - Return available test users and scenarios."""
    container: WebContainer = request.app["container"]
    if not container.config.enable_simulator or not container.simulator_service:
        return web.json_response({"users": [], "presets": []})

    return web.json_response(
        {
            "users": PRESET_USERS,
            "presets": container.simulator_service.get_presets(),
        }
    )
