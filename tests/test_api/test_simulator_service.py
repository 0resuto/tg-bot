"""Tests for the interactive ChatSimulatorService pipeline."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from bot.api.services.simulator_service import SIMULATOR_CHAT_ID, ChatSimulatorService
from bot.config import Settings
from bot.services.mention_detector import MentionDetector


def _settings(**overrides: object) -> Settings:
    base: dict[str, object] = {"_env_file": None, "bot_names": "Ista"}
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


def _build_service() -> tuple[ChatSimulatorService, dict[str, MagicMock]]:
    mocks: dict[str, MagicMock] = {
        "member_repo": MagicMock(),
        "context_builder": MagicMock(),
        "debouncer": MagicMock(),
        "response_service": MagicMock(),
    }
    mocks["member_repo"].upsert_member = AsyncMock()
    mocks["context_builder"].add_message = AsyncMock()
    mocks["context_builder"].get_context = AsyncMock(return_value=[])
    mocks["debouncer"].on_message = AsyncMock()
    mocks["response_service"].generate_response = AsyncMock(return_value="Привет!")

    service = ChatSimulatorService(
        settings=_settings(),
        member_repo=mocks["member_repo"],
        context_builder=mocks["context_builder"],
        debouncer=mocks["debouncer"],
        mention_detector=MentionDetector(
            bot_names=["Ista"], bot_user_id=999999999, bot_username="ista_bot"
        ),
        response_service=mocks["response_service"],
        admin_notifier=None,
    )
    return service, mocks


@pytest.mark.asyncio
async def test_unaddressed_message_is_observed_without_response():
    service, mocks = _build_service()

    result = await service.send_simulated_message(user_id=1, user_name="Alice", text="привет всем")

    assert result["success"] is True
    assert result["is_addressed"] is False
    assert result["bot_reply"] is None
    assert result["bot_status"] == "ready"
    mocks["response_service"].generate_response.assert_not_awaited()
    mocks["context_builder"].add_message.assert_awaited_once()
    mocks["debouncer"].on_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_message_addressed_by_name_triggers_response():
    service, mocks = _build_service()

    result = await service.send_simulated_message(
        user_id=2, user_name="Bob", text="Ista, что любит Алиса?"
    )

    assert result["is_addressed"] is True
    assert result["bot_reply"] == "Привет!"
    assert result["bot_status"] == "ready"

    kwargs = mocks["response_service"].generate_response.await_args.kwargs
    assert kwargs["chat_id"] == SIMULATOR_CHAT_ID
    assert kwargs["raise_on_error"] is True
    assert mocks["context_builder"].add_message.await_count == 2


@pytest.mark.asyncio
async def test_reply_to_bot_triggers_response():
    service, mocks = _build_service()

    result = await service.send_simulated_message(
        user_id=1, user_name="Alice", text="а подробнее?", reply_to_bot=True
    )

    assert result["is_addressed"] is True
    mocks["response_service"].generate_response.assert_awaited_once()


@pytest.mark.asyncio
async def test_llm_failure_is_reported_without_crashing():
    service, mocks = _build_service()
    mocks["response_service"].generate_response = AsyncMock(side_effect=RuntimeError("boom"))

    result = await service.send_simulated_message(user_id=1, user_name="Alice", text="Ista, привет")

    assert result["success"] is True
    assert result["bot_reply"] == "[LLM Error: boom]"
    assert result["bot_status"] == "error"
    assert service.last_error == "boom"


@pytest.mark.asyncio
async def test_degraded_stack_reports_simulator_error():
    service = ChatSimulatorService(
        settings=_settings(),
        member_repo=None,
        context_builder=None,
        debouncer=None,
        mention_detector=None,
        response_service=None,
        admin_notifier=None,
    )

    result = await service.send_simulated_message(
        user_id=1, user_name="Alice", text="любой текст", reply_to_bot=True
    )

    assert result["success"] is True
    assert result["is_addressed"] is True
    assert result["bot_status"] == "error"
    assert "Simulator Error" in result["bot_reply"]


def test_presets_include_bot_name_prompt():
    service, _ = _build_service()

    presets = service.get_presets()

    assert any("Ista" in preset["text"] for preset in presets)
