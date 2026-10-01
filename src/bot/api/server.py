"""Application factory and runner for web dashboard server."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from starlette.staticfiles import StaticFiles

from bot.api.dependencies import WebContainer
from bot.api.router import router
from bot.config import Settings, WebConfig
from bot.log import get_logger, setup_logging

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage WebContainer initialization and disposal lifecycle."""
    container: WebContainer = app.state.container
    if not container.is_initialized:
        await container.init()
    try:
        yield
    finally:
        await container.dispose()


def create_web_app(
    settings: Settings | None = None,
    config: WebConfig | None = None,
    container: WebContainer | None = None,
) -> FastAPI:
    """Instantiate and configure the FastAPI web dashboard application."""
    settings = settings or Settings()
    config = config or (container.config if container else WebConfig())
    container = container or WebContainer(settings=settings, config=config)

    app = FastAPI(
        title="Telegram Memory Bot Dashboard",
        description="Admin dashboard and knowledge graph visualizer for Telegram Memory Bot",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.container = container

    # CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    # Core Dashboard & Simulator API Routes
    app.include_router(router)

    # Static Assets & SPA Routing
    dist_dir = config.static_dir
    if dist_dir.is_dir():
        assets_dir = dist_dir / "assets"
        if assets_dir.is_dir():
            app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")
        app.mount("/static", StaticFiles(directory=dist_dir), name="static")
    elif config.dev_static_dir.is_dir():
        app.mount("/static", StaticFiles(directory=config.dev_static_dir), name="static")

    @app.get("/", response_model=None)
    async def serve_index() -> FileResponse | JSONResponse:
        """Serve the single-page application index HTML."""
        dist_index = config.static_dir / "index.html"
        if dist_index.is_file():
            return FileResponse(dist_index)

        dev_index = config.dev_static_dir / "index.html"
        if dev_index.is_file():
            return FileResponse(dev_index)

        return JSONResponse(
            status_code=404,
            content={"error": "Frontend build not found. Run 'npm run build' inside frontend/."},
        )

    return app


def run_web_server(config: WebConfig | None = None) -> None:
    """CLI runner executing the uvicorn ASGI server."""
    config = config or Settings().to_web_config()
    setup_logging(debug=True)

    mode_name = "SIMULATOR + DASHBOARD" if config.enable_simulator else "PRODUCTION DASHBOARD"
    print("\n=======================================================")
    print(f"  Telegram Memory Bot - {mode_name}")
    print(f"  Simulator Active: {config.enable_simulator}")
    print(f"  Serving at: http://{config.host}:{config.port}")
    print(f"  API Docs (Swagger): http://{config.host}:{config.port}/docs")
    print("=======================================================\n")

    app = create_web_app(config=config)
    try:
        uvicorn.run(app, host=config.host, port=config.port, log_level="info")
    except OSError as err:
        if "10048" in str(err) or "already in use" in str(err).lower():
            print(f"\n[ERROR] Port {config.port} is already busy.")
            print(f"Try running with another port, e.g. --port {config.port + 1}\n")
        raise
