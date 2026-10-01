"""Tests for SystemHealthService connectivity checks."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.api.services.health_service import SystemHealthService
from bot.config import Settings


def _settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "_env_file": None,
        "openai_api_key": "sk-test",
        "openai_response_model": "gpt-4o",
        "neo4j_password": "neo-pass",
        "postgres_password": "pg-pass",
        "redis_url": "redis://fake:6379/0",
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_check_all_ready_when_all_services_respond():
    engine = MagicMock()
    connection = AsyncMock()
    engine.connect.return_value.__aenter__ = AsyncMock(return_value=connection)
    engine.connect.return_value.__aexit__ = AsyncMock(return_value=False)
    engine.dispose = AsyncMock()

    redis_client = MagicMock()
    redis_client.ping = AsyncMock()
    redis_client.aclose = AsyncMock()

    neo4j_driver = MagicMock()
    neo4j_driver.verify_connectivity = AsyncMock()
    neo4j_driver.close = AsyncMock()

    with (
        patch("bot.api.services.health_service.create_async_engine_instance", return_value=engine),
        patch("bot.api.services.health_service.aioredis.from_url", return_value=redis_client),
        patch("bot.api.services.health_service.AsyncGraphDatabase") as async_db,
    ):
        async_db.driver.return_value = neo4j_driver
        data = await SystemHealthService(_settings()).check_all()

    assert data["all_ready"] is True
    assert {item["id"] for item in data["items"]} == {"openai", "postgres", "redis", "neo4j"}
    assert all(item["status"] == "ok" for item in data["items"])
    engine.dispose.assert_awaited_once()
    redis_client.aclose.assert_awaited_once()
    neo4j_driver.verify_connectivity.assert_awaited_once()
    neo4j_driver.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_check_all_flags_missing_credentials_and_failures():
    with (
        patch(
            "bot.api.services.health_service.create_async_engine_instance",
            side_effect=RuntimeError("pg down"),
        ),
        patch(
            "bot.api.services.health_service.aioredis.from_url",
            side_effect=RuntimeError("redis down"),
        ),
    ):
        data = await SystemHealthService(
            _settings(openai_api_key="", neo4j_password="")
        ).check_all()

    statuses = {item["id"]: item["status"] for item in data["items"]}
    assert statuses == {"openai": "error", "postgres": "error", "redis": "error", "neo4j": "error"}
    assert data["all_ready"] is False

    by_id = {item["id"]: item for item in data["items"]}
    assert "OPENAI_API_KEY" in by_id["openai"]["error"]
    assert "NEO4J_PASSWORD" in by_id["neo4j"]["error"]
    assert "pg down" in by_id["postgres"]["error"]
    assert "redis down" in by_id["redis"]["error"]
