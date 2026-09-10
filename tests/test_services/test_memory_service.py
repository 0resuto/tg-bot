from __future__ import annotations

from datetime import datetime

import pytest

from bot.domain.models import ChatMessage
from bot.services.memory_service import MemoryService
from bot.services.sensitive_filter import SensitiveFilter
from tests.conftest import MockMemoryBackend, MockTokenUsageRepo


@pytest.fixture
def sensitive_filter():
    class DummyFilter(SensitiveFilter):
        def __init__(self):
            super().__init__(enabled=True, categories=[])

        def filter_for_ingestion(self, text):
            if "password" in text:
                return None, []
            return text, []

    return DummyFilter()


@pytest.fixture
def memory_service(fake_redis, sensitive_filter):
    backend = MockMemoryBackend()
    token_repo = MockTokenUsageRepo()
    return MemoryService(
        memory=backend,
        sensitive_filter=sensitive_filter,
        token_repo=token_repo,
        redis=fake_redis,
        cache_ttl=60,
        search_limit_quick=5,
        search_limit_deep=15,
    )


async def test_ingest_messages(memory_service):
    msg = ChatMessage(
        chat_id=1,
        user_id=10,
        text="hello",
        timestamp=datetime.now(),
        message_id=100,
        display_name="Alice",
        reply_to_message_id=None,
    )
    await memory_service.ingest_messages(1, 10, [msg])
    assert len(memory_service.memory.episodes) == 1
    assert "hello" in memory_service.memory.episodes[0]["text"]


async def test_ingest_messages_skips_sensitive(memory_service):
    msg = ChatMessage(
        chat_id=1,
        user_id=10,
        text="my password is foo",
        timestamp=datetime.now(),
        message_id=100,
        display_name="Alice",
        reply_to_message_id=None,
    )
    await memory_service.ingest_messages(1, 10, [msg])
    assert len(memory_service.memory.episodes) == 0


async def test_get_quick_facts(memory_service):
    facts1 = await memory_service.get_quick_facts("Alice", 1)
    assert len(facts1) == 1
    assert facts1[0].fact_text == "likes coffee"

    facts2 = await memory_service.get_quick_facts("Alice", 1)
    assert len(facts2) == 1


async def test_search_memories(memory_service):
    facts = await memory_service.search_memories("coffee", 1)
    assert len(facts) == 1
    assert facts[0].fact_text == "likes coffee"


async def test_forget_fact(memory_service):
    count = await memory_service.forget_fact("coffee", 1)
    assert count == 1
    assert len(memory_service.memory.facts) == 0
