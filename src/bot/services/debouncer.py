"""In-memory sliding-window message debouncer for episodic LLM memory ingestion."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from bot.domain.models import ChatMessage
from bot.log import get_logger

logger = get_logger(__name__)


class MessageDebouncer:
    """Buffers consecutive messages from the same speaker in memory before flushing."""

    def __init__(
        self,
        debounce_seconds: float = 10.0,
        on_flush: Callable[[int, int, list[ChatMessage]], Awaitable[None]] | None = None,
    ) -> None:
        self.debounce_seconds = debounce_seconds
        self.on_flush = on_flush
        self._buffers: dict[tuple[int, int], list[ChatMessage]] = {}
        self._timers: dict[tuple[int, int], asyncio.TimerHandle] = {}
        self._processing: set[tuple[int, int]] = set()
        self._tasks: set[asyncio.Task[None]] = set()

    async def on_message(self, message: ChatMessage) -> None:
        """Buffer an incoming message and reset the sliding debounce timer."""
        key = (message.chat_id, message.user_id)

        # 1. Append message to in-memory buffer
        if key not in self._buffers:
            self._buffers[key] = []
        self._buffers[key].append(message)

        # 2. Cancel existing timer if running
        timer = self._timers.get(key)
        if timer is not None:
            timer.cancel()

        # 3. Schedule flush after debounce_seconds of silence
        loop = asyncio.get_running_loop()
        self._timers[key] = loop.call_later(
            self.debounce_seconds,
            self._schedule_flush,
            message.chat_id,
            message.user_id,
        )

    def _schedule_flush(self, chat_id: int, user_id: int) -> None:
        """Create a tracked background task to flush the user's buffered messages."""
        task = asyncio.create_task(
            self._flush(chat_id, user_id),
            name=f"debouncer_flush_{chat_id}_{user_id}",
        )
        self._tasks.add(task)
        task.add_done_callback(self._on_task_done)

    def _on_task_done(self, task: asyncio.Task[None]) -> None:
        self._tasks.discard(task)
        if not task.cancelled() and task.exception():
            logger.error("Debouncer flush task failed", exc_info=task.exception())

    async def _flush(self, chat_id: int, user_id: int) -> None:
        """Drain buffered messages and invoke the on_flush callback."""
        key = (chat_id, user_id)

        # Cancel and clean up timer reference
        timer = self._timers.pop(key, None)
        if timer is not None:
            timer.cancel()

        # If an ingestion for this user is already active, defer until it finishes
        if key in self._processing:
            return

        # Pop current batch from buffer
        messages = self._buffers.pop(key, [])
        if not messages or self.on_flush is None:
            return

        self._processing.add(key)
        try:
            await self.on_flush(chat_id, user_id, messages)
        except Exception as exc:
            logger.error(
                "Error in debouncer on_flush callback",
                exc_info=exc,
                chat_id=chat_id,
                user_id=user_id,
            )
        finally:
            self._processing.discard(key)
            # If new messages arrived while on_flush was awaiting, schedule next flush
            if self._buffers.get(key) and key not in self._timers:
                loop = asyncio.get_running_loop()
                self._timers[key] = loop.call_later(
                    self.debounce_seconds,
                    self._schedule_flush,
                    chat_id,
                    user_id,
                )

    async def shutdown(self) -> None:
        """Cancel all pending timers and flush remaining buffered messages concurrently."""
        for timer in self._timers.values():
            timer.cancel()
        self._timers.clear()

        # Collect all remaining keys
        pending_keys = [k for k, msgs in self._buffers.items() if msgs]
        if pending_keys:
            tasks = [self._flush(chat_id, user_id) for chat_id, user_id in pending_keys]
            await asyncio.gather(*tasks, return_exceptions=True)

        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
