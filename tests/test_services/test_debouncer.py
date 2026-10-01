from __future__ import annotations

import asyncio
from datetime import datetime

import pytest

from bot.models import ChatMessage
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


async def test_debouncer_closed_drops_incoming_messages(debouncer):
    await debouncer.shutdown()
    assert debouncer._closed is True

    # Sending a message after shutdown
    msg = ChatMessage(1, 10, "late message", datetime.now(), 300, "Alice", None)
    await debouncer.on_message(msg)

    # Should not create buffer or timer
    assert (1, 10) not in debouncer._buffers
    assert (1, 10) not in debouncer._timers


async def test_debouncer_max_debounce_seconds_window_cap():
    flushed = []

    async def on_flush(chat_id, user_id, messages):
        flushed.append(messages)

    # debounce_seconds = 0.2, but max_debounce_seconds = 0.3
    d = MessageDebouncer(debounce_seconds=0.2, max_debounce_seconds=0.3, on_flush=on_flush)

    # Send first message at t=0
    await d.on_message(ChatMessage(1, 10, "msg 1", datetime.now(), 401, "Alice", None))

    # Send second message at t=0.15 (resets sliding timer, but capped at 0.3 from start)
    await asyncio.sleep(0.15)
    await d.on_message(ChatMessage(1, 10, "msg 2", datetime.now(), 402, "Alice", None))

    # Send third message at t=0.25 (should flush at or before t=0.30, not t=0.45)
    await asyncio.sleep(0.10)
    await d.on_message(ChatMessage(1, 10, "msg 3", datetime.now(), 403, "Alice", None))

    # Wait until t=0.35 total (exceeds max_debounce_seconds 0.3)
    await asyncio.sleep(0.12)
    assert len(flushed) == 1
    assert len(flushed[0]) == 3
    await d.shutdown()
