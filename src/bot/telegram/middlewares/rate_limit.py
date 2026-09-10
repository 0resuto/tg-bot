"""
Rate limit middleware.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Any

import redis.asyncio
import structlog
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

logger = structlog.get_logger(__name__)


class RateLimitMiddleware(BaseMiddleware):
    def __init__(self, redis: redis.asyncio.Redis, max_per_minute: int):
        self.redis = redis
        self.max_per_minute = max_per_minute

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        chat = data.get("event_chat")
        user = data.get("event_from_user")

        if chat and user:
            key = f"ratelimit:{chat.id}:{user.id}"
            now = time.time()
            window_start = now - 60.0

            pipeline = self.redis.pipeline()
            pipeline.zadd(key, {str(now): now})
            pipeline.zremrangebyscore(key, "-inf", window_start)
            pipeline.zcard(key)
            pipeline.expire(key, 60)

            try:
                results = await pipeline.execute()
                count = results[2]
                if count > self.max_per_minute:
                    logger.warning("Rate limit exceeded", chat_id=chat.id, user_id=user.id)
                    return None
            except Exception as e:
                logger.error("Rate limiting failed", error=str(e))
                # Fail open if Redis fails

        return await handler(event, data)
