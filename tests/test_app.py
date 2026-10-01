"""Smoke tests for the application entrypoint wiring."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.app import main

VALID_ENV = {
    "TELEGRAM_BOT_TOKEN": "123:ABC",
    "OPENAI_API_KEY": "sk-test",
    "POSTGRES_PASSWORD": "pg-pass",
    "NEO4J_PASSWORD": "neo-pass",
    "GROUP_CHAT_ID": "-100123",
    "ADMIN_USER_ID": "42",
}


@pytest.mark.asyncio
async def test_main_wires_services_and_starts_polling():
    """main() must assemble the full service graph and start polling."""
    with patch.dict(os.environ, VALID_ENV, clear=True):
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
    dp.start_polling.assert_awaited_once()
