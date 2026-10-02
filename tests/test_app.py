"""Smoke tests for the application entrypoint wiring."""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.app import build_bot_session, main

VALID_ENV = {
    "TELEGRAM_BOT_TOKEN": "123:ABC",
    "OPENAI_API_KEY": "sk-test",
    "POSTGRES_PASSWORD": "pg-pass",
    "NEO4J_PASSWORD": "neo-pass",
    "GROUP_CHAT_ID": "-100123",
    "ADMIN_USER_ID": "42",
}


@contextmanager
def patched_io() -> Iterator[tuple[MagicMock, MagicMock, MagicMock]]:
    """Patch external I/O used by main(); yield (bot_cls, dispatcher_factory, redis)."""
    engine = MagicMock()
    engine.dispose = AsyncMock()
    redis_client = MagicMock()
    redis_client.aclose = AsyncMock()

    with (
        patch("bot.app.create_async_engine_instance", return_value=engine),
        patch("bot.app.create_session_factory"),
        patch("bot.app.create_redis_client", return_value=redis_client),
        patch("bot.app.GraphitiMemoryBackend") as memory_backend_cls,
        patch("bot.app.OpenAILLMProvider") as llm_cls,
        patch("bot.app.Bot") as bot_cls,
        patch("bot.app.create_dispatcher") as dispatcher_factory,
    ):
        llm_cls.return_value.close = AsyncMock()
        memory_backend_cls.return_value.close = AsyncMock()

        dp = dispatcher_factory.return_value
        dp.startup.return_value = lambda func: func
        dp.shutdown.return_value = lambda func: func
        dp.start_polling = AsyncMock()

        yield bot_cls, dispatcher_factory, redis_client


@pytest.mark.asyncio
async def test_main_wires_services_and_starts_polling():
    """main() must assemble the full service graph and start polling."""
    with (
        patch.dict(os.environ, VALID_ENV, clear=True),
        patched_io() as (bot_cls, dispatcher_factory, redis_client),
    ):
        await main()

    dispatcher_factory.assert_called_once()
    settings = dispatcher_factory.call_args.args[0]
    services = dispatcher_factory.call_args.args[1]
    assert dispatcher_factory.call_args.args[2] is redis_client

    expected_services = {
        "memory_service",
        "response_service",
        "context_builder",
        "debouncer",
        "member_repo",
        "admin_notifier",
        "settings",
    }
    assert expected_services <= set(services)
    assert settings.group_chat_id == -100123

    bot_cls.assert_called_once()
    assert bot_cls.call_args.kwargs["session"] is None
    dispatcher_factory.return_value.start_polling.assert_awaited_once()


@pytest.mark.asyncio
async def test_main_passes_configured_proxy_to_bot_session():
    """TELEGRAM_PROXY_URL must be wired into the aiogram Bot session."""
    env = {**VALID_ENV, "TELEGRAM_PROXY_URL": "socks5://127.0.0.1:1080"}
    with (
        patch.dict(os.environ, env, clear=True),
        patched_io() as (bot_cls, _, _),
        patch("bot.app.build_bot_session") as build_session,
    ):
        await main()

    build_session.assert_called_once_with("socks5://127.0.0.1:1080")
    assert bot_cls.call_args.kwargs["session"] is build_session.return_value


def test_build_bot_session_returns_none_without_proxy():
    assert build_bot_session("") is None
    assert build_bot_session("   ") is None


def test_build_bot_session_strips_proxy_url():
    with patch("bot.app.AiohttpSession") as session_cls:
        session = build_bot_session("  socks5://127.0.0.1:1080  ")

    session_cls.assert_called_once_with(proxy="socks5://127.0.0.1:1080")
    assert session is session_cls.return_value
