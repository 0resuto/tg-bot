"""
Admin group chat handlers.
"""

from __future__ import annotations

from aiogram import Router

from bot.config import Settings  # type: ignore
from bot.telegram.filters.admin import IsAdminUser

admin_group_router = Router(name="admin_group")


def setup_admin_group_router(settings: Settings) -> None:
    admin_group_router.message.filter(IsAdminUser(settings.admin_user_id))
