from __future__ import annotations

from datetime import datetime

import pytest

from bot.models import ChatMessage, MemoryFact
from bot.services.memory_service import MemoryService
from tests.conftest import MockMemoryBackend


@pytest.fixture
def memory_service():
    backend = MockMemoryBackend()
    return MemoryService(
        memory=backend,
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


async def test_ingest_messages_skips_pure_noise(memory_service):
    noise_msg1 = ChatMessage(
        chat_id=1,
        user_id=10,
        text="[Sticker 👍]",
        timestamp=datetime.now(),
        message_id=101,
        display_name="Alice",
    )
    noise_msg2 = ChatMessage(
        chat_id=1,
        user_id=10,
        text="ахаха",
        timestamp=datetime.now(),
        message_id=102,
        display_name="Alice",
    )
    await memory_service.ingest_messages(1, 10, [noise_msg1, noise_msg2])
    # Entire batch dropped, no episode created
    assert len(memory_service.memory.episodes) == 0


async def test_get_quick_facts(memory_service):
    facts1 = await memory_service.get_quick_facts("Alice", 1)
    assert len(facts1) == 1
    assert facts1[0].fact_text == "likes coffee"

    # Add a new fact to backend
    memory_service.memory.facts.append(MemoryFact(fact_text="owns a cat", subject_name="Alice"))

    # Immediately fetched without stale cache delay
    facts2 = await memory_service.get_quick_facts("Alice", 1)
    assert len(facts2) == 2
    assert {f.fact_text for f in facts2} == {"likes coffee", "owns a cat"}


async def test_search_memories(memory_service):
    facts = await memory_service.search_memories("coffee", 1)
    assert len(facts) == 1
    assert facts[0].fact_text == "likes coffee"
