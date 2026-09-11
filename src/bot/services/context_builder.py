from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import redis.asyncio as redis

from bot.domain.models import ChatMessage


class ContextBuilder:
    """Redis-backed recent message buffer for building conversation context."""

    def __init__(
        self,
        redis_client: redis.Redis,
        window_minutes: int = 15,
        min_messages: int = 10,
        max_buffer_size: int = 100,
        ttl_seconds: int = 86400 * 14,
    ) -> None:
        self.redis = redis_client
        self.window_minutes = window_minutes
        self.min_messages = min_messages
        self.max_buffer_size = max_buffer_size
        self.ttl_seconds = ttl_seconds

    async def add_message(self, msg: ChatMessage) -> None:
        """Push a message to the Redis list, trim to max_buffer_size, and set TTL."""
        redis_key = f"context:{msg.chat_id}"

        msg_dict = {
            "chat_id": msg.chat_id,
            "user_id": msg.user_id,
            "text": msg.text,
            "timestamp": msg.timestamp.isoformat(),
            "message_id": msg.message_id,
            "display_name": msg.display_name,
            "reply_to_message_id": msg.reply_to_message_id,
        }
        raw_msg = json.dumps(msg_dict)

        pipeline = self.redis.pipeline()
        pipeline.rpush(redis_key, raw_msg)
        pipeline.ltrim(redis_key, -self.max_buffer_size, -1)
        if self.ttl_seconds > 0:
            pipeline.expire(redis_key, self.ttl_seconds)
        await pipeline.execute()

    async def get_context(self, chat_id: int) -> list[ChatMessage]:
        """
        Returns messages matching: 'last N minutes, but at least M messages'.
        Messages are returned in chronological order.
        """
        redis_key = f"context:{chat_id}"
        raw_messages = await self.redis.lrange(redis_key, 0, -1)

        if not raw_messages:
            return []

        all_messages = []
        for raw_msg in raw_messages:
            data = json.loads(raw_msg)
            data["timestamp"] = datetime.fromisoformat(data["timestamp"])
            all_messages.append(ChatMessage(**data))

        now = datetime.now(UTC)
        cutoff_time = now - timedelta(minutes=self.window_minutes)

        def _as_utc(dt: datetime) -> datetime:
            return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)

        # Filter by timestamp
        recent_messages = [msg for msg in all_messages if _as_utc(msg.timestamp) >= cutoff_time]

        # If fewer than min_messages, extend to include at least min_messages
        if len(recent_messages) < self.min_messages:
            needed = self.min_messages
            # Take the last `needed` messages from all_messages
            recent_messages = all_messages[-needed:] if len(all_messages) > needed else all_messages

        return recent_messages
