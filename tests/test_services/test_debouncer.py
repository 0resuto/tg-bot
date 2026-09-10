from __future__ import annotations

import asyncio
from datetime import datetime

import pytest

from bot.domain.models import ChatMessage
from bot.services.debouncer import MessageDebouncer


@pytest.fixture
def debouncer(fake_redis):
    flushed_batches = []

    async def on_flush(chat_id, user_id, messages):
        flushed_batches.append((chat_id, user_id, messages))

    d = MessageDebouncer(fake_redis, debounce_seconds=0.1, on_flush=on_flush)
    d.flushed_batches = flushed_batches
    return d


async def test_debouncer_single_message(debouncer):
    msg = ChatMessage(1, 10, "hi", datetime.now(), 100, "Alice", None)
    await debouncer.on_message(msg)

    await asyncio.sleep(0.2)
    assert len(debouncer.flushed_batches) == 1
    assert debouncer.flushed_batches[0][0] == 1
    assert debouncer.flushed_batches[0][1] == 10
    assert len(debouncer.flushed_batches[0][2]) == 1


async def test_debouncer_multiple_messages(debouncer):
    msg1 = ChatMessage(1, 10, "hi", datetime.now(), 100, "Alice", None)
    msg2 = ChatMessage(1, 10, "there", datetime.now(), 101, "Alice", None)

    await debouncer.on_message(msg1)
    await debouncer.on_message(msg2)

    await asyncio.sleep(0.2)
    assert len(debouncer.flushed_batches) == 1
    assert len(debouncer.flushed_batches[0][2]) == 2
