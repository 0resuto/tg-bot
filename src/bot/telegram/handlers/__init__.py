"""
Telegram handlers package.
"""

from __future__ import annotations

from aiogram import Dispatcher

from bot.config import Settings  # type: ignore
from bot.telegram.handlers.admin_group import admin_group_router, setup_admin_group_router
from bot.telegram.handlers.admin_private import admin_private_router, setup_admin_private_router
from bot.telegram.handlers.chat_management import (
    chat_management_router,
    setup_chat_management_router,
)
from bot.telegram.handlers.group_messages import group_messages_router
from bot.telegram.handlers.user_commands import user_commands_router


def setup_routers(dp: Dispatcher, settings: Settings) -> None:
    setup_admin_private_router(settings)
    setup_admin_group_router(settings)
    setup_chat_management_router(admin_user_id=settings.admin_user_id)

    # Strict order: chat_management (join/leave + callbacks) -> admin -> commands -> catch-all
    dp.include_routers(
        chat_management_router,
        admin_private_router,
        admin_group_router,
        user_commands_router,
        group_messages_router,
    )
