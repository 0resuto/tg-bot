"""
Telegram handlers package.
"""

from __future__ import annotations

from aiogram import Dispatcher

from bot.config import Settings  # type: ignore
from bot.telegram.handlers.admin_group import admin_group_router, setup_admin_group_router
from bot.telegram.handlers.admin_private import admin_private_router, setup_admin_private_router
from bot.telegram.handlers.group_messages import group_messages_router
from bot.telegram.handlers.user_commands import user_commands_router


def setup_routers(dp: Dispatcher, settings: Settings) -> None:
    setup_admin_private_router(settings)
    setup_admin_group_router(settings)

    # Strict order: admin -> commands -> catch-all
    dp.include_routers(
        admin_private_router,
        admin_group_router,
        user_commands_router,
        group_messages_router,
    )
