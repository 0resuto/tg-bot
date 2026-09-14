"""
Dispatcher factory.
"""

from __future__ import annotations

from typing import Any

import redis.asyncio
from aiogram import Dispatcher
from aiogram.fsm.storage.redis import RedisStorage

from bot.config import Settings
from bot.telegram.handlers import setup_routers
from bot.telegram.middlewares.services import ServicesMiddleware


def create_dispatcher(
    settings: Settings, services: dict[str, Any], redis_client: redis.asyncio.Redis
) -> Dispatcher:
    # Use redis_client for storage
    storage = RedisStorage(redis=redis_client)
    dp = Dispatcher(storage=storage)

    # Inject services into message handlers
    services_mw = ServicesMiddleware(services=services)
    dp.message.middleware(services_mw)

    setup_routers(dp, settings)

    return dp
