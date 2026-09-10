"""
Admin filters for aiogram handlers.
"""

from __future__ import annotations

from aiogram.filters import Filter
from aiogram.types import Message


class IsAdminChat(Filter):
    def __init__(self, admin_chat_id: int):
        self.admin_chat_id = admin_chat_id

    async def __call__(self, message: Message) -> bool:
        return message.chat.id == self.admin_chat_id


class IsAdminUser(Filter):
    def __init__(self, admin_user_id: int):
        self.admin_user_id = admin_user_id

    async def __call__(self, message: Message) -> bool:
        return message.from_user is not None and message.from_user.id == self.admin_user_id
