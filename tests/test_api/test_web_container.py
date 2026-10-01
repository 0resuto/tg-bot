"""Tests for WebContainer service assembly and lifecycle."""

from __future__ import annotations

from contextlib import ExitStack
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.api.dependencies import WebContainer
from bot.config import Settings, WebConfig

FULL_STACK = {"openai": "ok", "postgres": "ok", "redis": "ok", "neo4j": "ok"}


def _settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "_env_file": None,
        "openai_api_key": "sk-test",
        "telegram_bot_token": "123:ABC",
        "postgres_password": "pg-pass",
        "neo4j_password": "neo-pass",
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


def _build_container(
    statuses: dict[str, str] | None = None,
    settings: Settings | None = None,
    enable_simulator: bool = False,
) -> WebContainer:
    container = WebContainer(
        settings=settings or _settings(),
        config=WebConfig(enable_simulator=enable_simulator),
    )
    health = MagicMock()
    health.items = [
        {"id": service_id, "status": status}
        for service_id, status in (statuses or FULL_STACK).items()
    ]
    health.check_all = AsyncMock(return_value={})
    container.health_service = health
    return container


def _start_infra(stack: ExitStack) -> dict[str, MagicMock]:
    engine = MagicMock()
    engine.dispose = AsyncMock()
    session_factory = MagicMock()
    redis_client = MagicMock()
    redis_client.aclose = AsyncMock()
    memory_backend = MagicMock()
    memory_backend.close = AsyncMock()
    llm_provider = MagicMock()
    llm_provider.close = AsyncMock()
    neo4j_driver = MagicMock()
    neo4j_driver.close = AsyncMock()
    bot = MagicMock()
    bot.session.close = AsyncMock()

    stack.enter_context(
        patch("bot.api.dependencies.create_async_engine_instance", return_value=engine)
    )
    stack.enter_context(
        patch("bot.api.dependencies.create_session_factory", return_value=session_factory)
    )
    stack.enter_context(patch("bot.api.dependencies.aioredis.from_url", return_value=redis_client))
    stack.enter_context(
        patch("bot.api.dependencies.GraphitiMemoryBackend", return_value=memory_backend)
    )
    stack.enter_context(patch("bot.api.dependencies.OpenAILLMProvider", return_value=llm_provider))
    neo4j_db = stack.enter_context(patch("bot.api.dependencies.AsyncGraphDatabase"))
    neo4j_db.driver.return_value = neo4j_driver
    stack.enter_context(patch("aiogram.Bot", return_value=bot))

    return {
        "engine": engine,
        "session_factory": session_factory,
        "redis_client": redis_client,
        "memory_backend": memory_backend,
        "llm_provider": llm_provider,
        "neo4j_driver": neo4j_driver,
        "bot": bot,
    }


@pytest.mark.asyncio
async def test_init_assembles_full_service_graph():
    container = _build_container()
    with ExitStack() as stack:
        mocks = _start_infra(stack)
        await container.init()

    assert container.is_initialized is True
    assert container.engine is mocks["engine"]
    assert container.session_factory is mocks["session_factory"]
    assert container.member_repo is not None
    assert container.redis is mocks["redis_client"]
    assert container.context_builder is not None
    assert container.llm_provider is mocks["llm_provider"]
    assert container.neo4j_driver is mocks["neo4j_driver"]
    assert container.memory_backend is mocks["memory_backend"]
    assert container.memory_service is not None
    assert container.memory_query_service is not None
    assert container.response_service is not None
    assert container.graph_service.driver is mocks["neo4j_driver"]
    assert container.admin_notifier is not None
    assert container.bot is mocks["bot"]
    assert container.simulator_service is None


@pytest.mark.asyncio
async def test_init_degrades_gracefully_when_infrastructure_is_down():
    container = _build_container(
        statuses={"openai": "ok", "postgres": "error", "redis": "error", "neo4j": "error"}
    )
    with ExitStack() as stack:
        _start_infra(stack)
        await container.init()

    assert container.is_initialized is True
    assert container.engine is None
    assert container.session_factory is None
    assert container.member_repo is None
    assert container.redis is None
    assert container.context_builder is None
    assert container.neo4j_driver is None
    assert container.memory_backend is None
    assert container.memory_service is None
    assert container.response_service is None
    assert container.graph_service.driver is None
    assert container.admin_notifier is not None


@pytest.mark.asyncio
async def test_init_skips_openai_dependent_services_without_key():
    container = _build_container(settings=_settings(openai_api_key=""))
    with ExitStack() as stack:
        _start_infra(stack)
        await container.init()

    assert container.llm_provider is None
    assert container.memory_backend is None
    assert container.memory_service is None
    assert container.response_service is None
    assert container.neo4j_driver is not None


@pytest.mark.asyncio
async def test_init_enables_simulator_when_requested():
    container = _build_container(enable_simulator=True)
    with ExitStack() as stack:
        _start_infra(stack)
        await container.init()

    assert container.debouncer is not None
    assert container.simulator_service is not None
    assert container.simulator_service.context_builder is container.context_builder
    assert container.simulator_service.response_service is container.response_service


@pytest.mark.asyncio
async def test_dispose_closes_all_resources():
    container = _build_container(enable_simulator=True)
    with ExitStack() as stack:
        mocks = _start_infra(stack)
        await container.init()

    await container.dispose()

    assert container.is_initialized is False
    mocks["engine"].dispose.assert_awaited_once()
    mocks["redis_client"].aclose.assert_awaited_once()
    mocks["memory_backend"].close.assert_awaited_once()
    mocks["llm_provider"].close.assert_awaited_once()
    mocks["neo4j_driver"].close.assert_awaited_once()
    mocks["bot"].session.close.assert_awaited_once()
