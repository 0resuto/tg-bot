from __future__ import annotations

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
