"""
Admin group chat handlers.
"""

from __future__ import annotations

from aiogram import Router

from bot.config import Settings  # type: ignore
from bot.telegram.filters.admin import IsAdminChat, IsAdminUser

admin_group_router = Router(name="admin_group")


def setup_admin_group_router(settings: Settings) -> None:
    if settings.admin_chat_id:
        admin_group_router.message.filter(
            IsAdminChat(settings.admin_chat_id),
            IsAdminUser(settings.admin_user_id),
        )
    else:
        admin_group_router.message.filter(IsAdminUser(settings.admin_user_id))
