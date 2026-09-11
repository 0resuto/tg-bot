"""Controller returning structured runtime event logs."""

from __future__ import annotations

from aiohttp import web

from bot.web.dependencies import WebContainer


async def handle_get_logs(request: web.Request) -> web.Response:
    """GET /api/logs - Return circular buffer of recent diagnostic events."""
    container: WebContainer = request.app["container"]
    logs: list[dict[str, object]] = []

    if container.simulator_service:
        logs = list(reversed(container.simulator_service.logs))

    admin_alerts: list[dict[str, object]] = []
    notifier = getattr(container, "admin_notifier", None)
    if notifier and hasattr(notifier, "recent_alerts"):
        admin_alerts = list(reversed(notifier.recent_alerts))

    return web.json_response(
        {
            "current_status": container.simulator_service.current_status
            if container.simulator_service
            else "ready",
            "last_error": container.simulator_service.last_error
            if container.simulator_service
            else None,
            "logs": logs,
            "admin_alerts": admin_alerts,
        }
    )
