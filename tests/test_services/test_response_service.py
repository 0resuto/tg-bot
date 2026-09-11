from __future__ import annotations

from datetime import UTC

import pytest

from bot.services.response_service import ResponseService
from tests.conftest import MockLLMProvider, MockTokenUsageRepo


class MockContextBuilder:
    async def get_context(self, chat_id: int):
        return []


@pytest.fixture
def response_service(fake_redis):
    llm = MockLLMProvider()
    token_repo = MockTokenUsageRepo()

    # Mocking memory service
    class MockMem:
        async def get_quick_facts(self, *args, **kwargs):
            return []

        async def search_memories(self, *args, **kwargs):
            return []

    return ResponseService(
        llm=llm,
        memory_service=MockMem(),
        context_builder=MockContextBuilder(),
        token_repo=token_repo,
        persona_prompt="You are a bot.",
        response_model="test-model",
        bot_language="en",
    )


async def test_generate_response(response_service):
    res = await response_service.generate_response(1, "Alice", ["Alice", "Bob"])
    assert res == "Mock response"
    assert len(response_service.llm.calls) == 1
    assert "You are a bot" in response_service.llm.calls[0]["system_prompt"]


async def test_generate_response_with_memory_chat_ids():
    from bot.domain.models import ChatMessage, MemoryFact

    llm = MockLLMProvider()
    token_repo = MockTokenUsageRepo()

    queried_quick_chats = []
    queried_deep_chats = []

    class MockMultiMem:
        async def get_quick_facts(self, user_name: str, chat_id: int):
            queried_quick_chats.append((user_name, chat_id))
            if chat_id == -100:
                return [MemoryFact(fact_text=f"{user_name} likes coffee")]
            return []

        async def search_memories(self, query: str, chat_id: int):
            queried_deep_chats.append(chat_id)
            if chat_id == -100:
                return [MemoryFact(fact_text="Alice bought a bike in Rome")]
            return []

    class MockContextWithMessages:
        async def get_context(self, chat_id: int):
            from datetime import datetime

            return [
                ChatMessage(
                    chat_id=chat_id,
                    user_id=1,
                    text="Hello bot",
                    timestamp=datetime.now(UTC),
                    message_id=1,
                    display_name="Admin",
                )
            ]

    svc = ResponseService(
        llm=llm,
        memory_service=MockMultiMem(),
        context_builder=MockContextWithMessages(),
        token_repo=token_repo,
        persona_prompt="You are Ista.",
        response_model="test-model",
        bot_language="ru",
    )

    res = await svc.generate_response(
        chat_id=10,
        user_display_name="Admin",
        active_user_names=["Admin", "Alice"],
        memory_chat_ids=[10, -100],
    )
    assert res == "Mock response"
    assert len(llm.calls) == 1
    system_prompt = llm.calls[0]["system_prompt"]

    # Both chats were queried
    assert 10 in [c for _, c in queried_quick_chats]
    assert -100 in [c for _, c in queried_quick_chats]
    assert 10 in queried_deep_chats
    assert -100 in queried_deep_chats

    # Group facts were included in system prompt
    assert "Alice likes coffee" in system_prompt
    assert "Alice bought a bike in Rome" in system_prompt


async def test_generate_response_error_notifies_admin():
    from unittest.mock import AsyncMock, MagicMock

    llm = MockLLMProvider()
    llm.generate_response = AsyncMock(side_effect=RuntimeError("OpenAI API Down"))
    token_repo = MockTokenUsageRepo()

    mock_notifier = MagicMock()
    mock_notifier.notify_error = AsyncMock()

    class MockEmptyMem:
        async def get_quick_facts(self, *args, **kwargs):
            return []

        async def search_memories(self, *args, **kwargs):
            return []

    svc = ResponseService(
        llm=llm,
        memory_service=MockEmptyMem(),
        context_builder=MockContextBuilder(),
        token_repo=token_repo,
        persona_prompt="You are a bot.",
        response_model="test-model",
        bot_language="ru",
        admin_notifier=mock_notifier,
    )

    res = await svc.generate_response(
        chat_id=777, user_display_name="Bob", active_user_names=["Bob"]
    )
    assert res == "Извините, произошла ошибка при генерации ответа."
    assert mock_notifier.notify_error.call_count == 1
    call_kwargs = mock_notifier.notify_error.call_args.kwargs
    assert call_kwargs["chat_id"] == 777
    assert call_kwargs["user_display_name"] == "Bob"
    assert isinstance(call_kwargs["error"], RuntimeError)
