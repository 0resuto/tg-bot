"""
Telegram handlers package.
"""

from __future__ import annotations

from aiogram import Dispatcher

from bot.config import Settings
from bot.telegram.handlers.admin_private import admin_private_router, setup_admin_private_router
from bot.telegram.handlers.group_messages import (
    group_messages_router,
    setup_group_messages_router,
)


def setup_routers(dp: Dispatcher, settings: Settings) -> None:
    setup_admin_private_router(settings)
    setup_group_messages_router(settings)

    # Fixed dual-chat topology: admin private chat -> main group messages
    dp.include_routers(
        admin_private_router,
        group_messages_router,
    )
