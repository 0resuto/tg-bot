from __future__ import annotations

import asyncio
from datetime import datetime

import pytest

from bot.domain.models import ChatMessage
from bot.services.debouncer import MessageDebouncer


@pytest.fixture
def debouncer():
    flushed_batches = []

    async def on_flush(chat_id, user_id, messages):
        flushed_batches.append((chat_id, user_id, messages))

    d = MessageDebouncer(debounce_seconds=0.1, on_flush=on_flush)
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


async def test_debouncer_shutdown_flushes_pending(debouncer):
    msg = ChatMessage(1, 10, "shutting down soon", datetime.now(), 102, "Alice", None)
    await debouncer.on_message(msg)

    # Immediately shutdown without waiting for 0.1s debounce
    await debouncer.shutdown()

    assert len(debouncer.flushed_batches) == 1
    assert debouncer.flushed_batches[0][2][0].text == "shutting down soon"


async def test_debouncer_callback_exception_handled():
    async def failing_flush(chat_id, user_id, messages):
        raise RuntimeError("Ingestion backend failure")

    d = MessageDebouncer(debounce_seconds=0.05, on_flush=failing_flush)
    msg = ChatMessage(1, 10, "will fail", datetime.now(), 103, "Alice", None)
    await d.on_message(msg)

    await asyncio.sleep(0.15)
    # The debouncer handled the exception safely
    await d.shutdown()
