"""Application factory and runner for web dashboard server."""

from __future__ import annotations

from aiohttp import web

from bot.config import Settings
from bot.log import get_logger, setup_logging
from bot.web.config import WebConfig
from bot.web.controllers.chats_controller import handle_get_chats
from bot.web.controllers.context_controller import handle_get_context
from bot.web.controllers.graph_controller import handle_get_graph
from bot.web.controllers.health_controller import handle_get_health
from bot.web.controllers.logs_controller import handle_get_logs
from bot.web.controllers.memory_controller import handle_get_memories, handle_post_forget
from bot.web.controllers.simulator_controller import (
    handle_get_presets,
    handle_send_message,
)
from bot.web.controllers.stats_controller import handle_get_stats
from bot.web.dependencies import WebContainer

logger = get_logger(__name__)


async def handle_index(request: web.Request) -> web.FileResponse:
    """Serve the single-page application index HTML."""
    container: WebContainer = request.app["container"]
    dist_index = container.config.static_dir / "index.html"
    if dist_index.is_file():
        return web.FileResponse(dist_index)

    dev_index = container.config.dev_static_dir / "index.html"
    if dev_index.is_file():
        return web.FileResponse(dev_index)

    raise web.HTTPNotFound(text="Frontend build not found. Run 'npm run build' inside frontend/.")


def create_web_app(
    settings: Settings | None = None,
    config: WebConfig | None = None,
    container: WebContainer | None = None,
) -> web.Application:
    """Instantiate and configure the aiohttp web dashboard application."""
    settings = settings or Settings()
    config = config or (container.config if container else WebConfig())
    container = container or WebContainer(settings=settings, config=config)

    app = web.Application()
    app["container"] = container

    async def on_startup(app_instance: web.Application) -> None:
        if not container.is_initialized:
            await container.init()

    async def on_cleanup(app_instance: web.Application) -> None:
        await container.dispose()

    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)

    # Core Dashboard Endpoints
    app.router.add_get("/", handle_index)
    app.router.add_get("/api/checklist", handle_get_health)
    app.router.add_get("/api/health", handle_get_health)
    app.router.add_get("/api/chats", handle_get_chats)
    app.router.add_get("/api/graph", handle_get_graph)
    app.router.add_get("/api/memories", handle_get_memories)
    app.router.add_post("/api/forget", handle_post_forget)
    app.router.add_get("/api/context", handle_get_context)
    app.router.add_get("/api/stats", handle_get_stats)
    app.router.add_get("/api/logs", handle_get_logs)

    # Chat Simulator Endpoints (Guarded by controller when disabled)
    app.router.add_post("/api/simulator/send_message", handle_send_message)
    app.router.add_get("/api/simulator/presets", handle_get_presets)
    # Backward compatibility alias
    app.router.add_post("/api/send_message", handle_send_message)

    # Static Assets
    dist_dir = config.static_dir
    if dist_dir.is_dir():
        app.router.add_static("/assets/", path=dist_dir / "assets", show_index=False)
        app.router.add_static("/static/", path=dist_dir, show_index=False)
    elif config.dev_static_dir.is_dir():
        app.router.add_static("/static/", path=config.dev_static_dir, show_index=False)

    return app


def run_web_server(config: WebConfig | None = None) -> None:
    """CLI runner executing the aiohttp server loop."""
    config = config or WebConfig()
    setup_logging(debug=True)

    mode_name = "SIMULATOR + DASHBOARD" if config.enable_simulator else "PRODUCTION DASHBOARD"
    print("\n=======================================================")
    print(f"  Telegram Memory Bot - {mode_name}")
    print(f"  Simulator Active: {config.enable_simulator}")
    print(f"  Serving at: http://{config.host}:{config.port}")
    print("=======================================================\n")

    app = create_web_app(config=config)
    try:
        web.run_app(app, host=config.host, port=config.port, reuse_address=True)
    except OSError as err:
        if "10048" in str(err) or "already in use" in str(err).lower():
            print(f"\n[ERROR] Port {config.port} is already busy.")
            print(f"Try running with another port, e.g. --port {config.port + 1}\n")
        raise
