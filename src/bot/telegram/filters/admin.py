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
        return bool(
            self.admin_chat_id != 0
            and message.chat is not None
            and message.chat.id == self.admin_chat_id
        )


class IsAdminUser(Filter):
    def __init__(self, admin_user_id: int | set[int] | list[int] | tuple[int, ...]):
        if isinstance(admin_user_id, set | list | tuple):
            self.admin_user_ids = {uid for uid in admin_user_id if uid > 0}
        else:
            self.admin_user_ids = {admin_user_id} if admin_user_id > 0 else set()

    async def __call__(self, message: Message) -> bool:
        return (
            bool(self.admin_user_ids)
            and message.from_user is not None
            and message.from_user.id in self.admin_user_ids
        )


class IsGroupChat(Filter):
    def __init__(self, group_chat_id: int):
        self.group_chat_id = group_chat_id

    async def __call__(self, message: Message) -> bool:
        return bool(
            self.group_chat_id != 0
            and message.chat is not None
            and message.chat.id == self.group_chat_id
        )
