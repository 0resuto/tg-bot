"""Tests for the FastAPI app factory, SPA serving, lifespan, and CLI env wiring."""

from __future__ import annotations

import sys
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from bot.api.dependencies import WebContainer
from bot.api.server import create_web_app
from bot.config import WebConfig


def _container() -> MagicMock:
    container = MagicMock(spec=WebContainer)
    container.is_initialized = True
    container.config = WebConfig()
    container.health_service = MagicMock()
    container.health_service.items = []
    container.health_service.all_ready = True
    return container


@pytest.mark.asyncio
async def test_index_returns_404_without_frontend_build(tmp_path):
    container = _container()
    config = WebConfig(static_dir=tmp_path / "dist", dev_static_dir=tmp_path / "dev")
    app = create_web_app(container=container, config=config)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/")

    assert resp.status_code == 404
    assert "Frontend build not found" in resp.json()["error"]


@pytest.mark.asyncio
async def test_index_serves_built_spa(tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html><body>dashboard</body></html>", encoding="utf-8")
    container = _container()
    config = WebConfig(static_dir=dist, dev_static_dir=tmp_path / "dev")
    app = create_web_app(container=container, config=config)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/")

    assert resp.status_code == 200
    assert "dashboard" in resp.text


@pytest.mark.asyncio
async def test_lifespan_initializes_and_disposes_container():
    container = _container()
    container.is_initialized = False
    container.init = AsyncMock()
    container.dispose = AsyncMock()
    app = create_web_app(container=container, config=container.config)

    async with app.router.lifespan_context(app):
        container.init.assert_awaited_once()

    container.dispose.assert_awaited_once()


def _run_api_main(monkeypatch, argv: list[str]) -> WebConfig:
    captured: dict[str, WebConfig] = {}
    monkeypatch.setattr(sys, "argv", argv)
    monkeypatch.setattr(
        "bot.api.__main__.run_web_server", lambda config: captured.update(config=config)
    )
    from bot.api.__main__ import main

    main()
    return captured["config"]


def test_api_main_uses_web_env_defaults(monkeypatch):
    monkeypatch.setenv("WEB_HOST", "0.0.0.0")
    monkeypatch.setenv("WEB_PORT", "9091")
    monkeypatch.setenv("WEB_ENABLE_SIMULATOR", "true")

    config = _run_api_main(monkeypatch, ["bot.api"])

    assert config.host == "0.0.0.0"
    assert config.port == 9091
    assert config.enable_simulator is True


def test_api_main_cli_overrides_env(monkeypatch):
    monkeypatch.setenv("WEB_HOST", "0.0.0.0")
    monkeypatch.setenv("WEB_PORT", "9091")

    config = _run_api_main(monkeypatch, ["bot.api", "--host", "1.2.3.4", "--port", "1234"])

    assert config.host == "1.2.3.4"
    assert config.port == 1234
    assert config.enable_simulator is False
