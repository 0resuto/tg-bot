"""Controller providing aggregated overview KPIs and runtime metrics."""

from __future__ import annotations

from aiohttp import web

from bot.web.dependencies import WebContainer
from bot.web.services.simulator_service import SIMULATOR_CHAT_ID


async def handle_get_stats(request: web.Request) -> web.Response:
    """GET /api/stats?chat_id=... - Return operational stats and checklist."""
    container: WebContainer = request.app["container"]
    chat_id_param = request.query.get("chat_id")
    chat_id = (
        int(chat_id_param)
        if chat_id_param and chat_id_param.lstrip("-").isdigit()
        else (SIMULATOR_CHAT_ID if container.config.enable_simulator else None)
    )

    stats = {
        "all_ready": container.health_service.all_ready,
        "checklist": container.health_service.items,
        "llm_model": f"OpenAI ({container.settings.openai_response_model})",
        "memory_backend": "Graphiti (Neo4j)",
        "bot_names": container.settings.bot_name_list or ["Bot"],
        "enable_simulator": container.config.enable_simulator,
        "memory_stats": {"status": "offline"},
        "token_stats": {"today_tokens": 0, "month_tokens": 0},
    }

    if container.memory_query_service and chat_id is not None:
        metrics = await container.memory_query_service.get_stats(chat_id)
        stats.update(metrics)

    return web.json_response(stats)
