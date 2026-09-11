from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from datetime import datetime

import redis.asyncio as redis

from bot.domain.models import ChatMessage


class MessageDebouncer:
    """Redis-backed message debouncing."""

    def __init__(
        self,
        redis_client: redis.Redis,
        debounce_seconds: float,
        on_flush: Callable[[int, int, list[ChatMessage]], Awaitable[None]],
    ) -> None:
        self.redis = redis_client
        self.debounce_seconds = debounce_seconds
        self.on_flush = on_flush
        self._locks: dict[tuple[int, int], asyncio.Lock] = {}
        self._timers: dict[tuple[int, int], asyncio.TimerHandle] = {}

    def _get_lock(self, chat_id: int, user_id: int) -> asyncio.Lock:
        key = (chat_id, user_id)
        if key not in self._locks:
            self._locks[key] = asyncio.Lock()
        return self._locks[key]

    async def on_message(self, message: ChatMessage) -> None:
        """Add a message to the pending batch and reset the timer."""
        chat_id = message.chat_id
        user_id = message.user_id
        key = (chat_id, user_id)

        async with self._get_lock(chat_id, user_id):
            redis_key = f"debounce:{chat_id}:{user_id}"

            # Serialize message to JSON
            # Need to convert datetime to isoformat
            msg_dict = {
                "chat_id": message.chat_id,
                "user_id": message.user_id,
                "text": message.text,
                "timestamp": message.timestamp.isoformat(),
                "message_id": message.message_id,
                "display_name": message.display_name,
                "reply_to_message_id": message.reply_to_message_id,
            }
            await self.redis.rpush(redis_key, json.dumps(msg_dict))

            # Reset timer
            if key in self._timers:
                self._timers[key].cancel()

            loop = asyncio.get_running_loop()
            self._timers[key] = loop.call_later(
                self.debounce_seconds, lambda: asyncio.create_task(self._flush(chat_id, user_id))
            )

    async def _flush(self, chat_id: int, user_id: int) -> None:
        """Pop all messages from Redis list, deserialize, and call on_flush."""
        async with self._get_lock(chat_id, user_id):
            redis_key = f"debounce:{chat_id}:{user_id}"

            # Retrieve and clear list atomically using pipeline or multi
            pipeline = self.redis.pipeline()
            pipeline.lrange(redis_key, 0, -1)
            pipeline.delete(redis_key)
            results = await pipeline.execute()

            raw_messages = results[0]
            if not raw_messages:
                return

            messages = []
            for raw_msg in raw_messages:
                data = json.loads(raw_msg)
                data["timestamp"] = datetime.fromisoformat(data["timestamp"])
                messages.append(ChatMessage(**data))

            # Clear timer reference
            key = (chat_id, user_id)
            if key in self._timers:
                del self._timers[key]

            # Call callback
            await self.on_flush(chat_id, user_id, messages)

    async def shutdown(self) -> None:
        """Flush all pending batches."""
        keys = list(self._timers.keys())
        for chat_id, user_id in keys:
            if (chat_id, user_id) in self._timers:
                self._timers[(chat_id, user_id)].cancel()
            await self._flush(chat_id, user_id)
