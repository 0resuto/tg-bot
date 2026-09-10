"""
Dispatcher factory.
"""

from __future__ import annotations

from typing import Any

import redis.asyncio
from aiogram import Dispatcher
from aiogram.fsm.storage.redis import RedisStorage

from bot.config import Settings  # type: ignore
from bot.telegram.handlers import setup_routers
from bot.telegram.middlewares.allowlist import ChatAllowlistMiddleware
from bot.telegram.middlewares.rate_limit import RateLimitMiddleware
from bot.telegram.middlewares.services import ServicesMiddleware


def create_dispatcher(
    settings: Settings, services: dict[str, Any], redis_client: redis.asyncio.Redis
) -> Dispatcher:
    # Use redis_client for storage
    storage = RedisStorage(redis=redis_client)
    dp = Dispatcher(storage=storage)

    initial_allowed = {settings.admin_chat_id} if settings.admin_chat_id else set()
    allowlist = ChatAllowlistMiddleware(allowed_chat_ids=initial_allowed)
    dp.update.outer_middleware(allowlist)
    dp["allowlist"] = allowlist

    rate_limiter = RateLimitMiddleware(
        redis=redis_client, max_per_minute=settings.rate_limit_messages_per_minute
    )
    dp.message.outer_middleware(rate_limiter)

    services_mw = ServicesMiddleware(services=services)
    dp.message.middleware(services_mw)

    setup_routers(dp, settings)

    return dp
