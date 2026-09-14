"""
Allowlist middleware.

Blocks updates from chats not in the allow-set, but always passes through
``my_chat_member`` updates so the bot can detect being added to new groups.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import ChatMemberUpdated, TelegramObject

from bot.log import get_logger

logger = get_logger(__name__)


class ChatAllowlistMiddleware(BaseMiddleware):
    def __init__(self, allowed_chat_ids: set[int]):
        self.allowed_chat_ids = allowed_chat_ids

    def add_chat(self, chat_id: int) -> None:
        """Dynamically add a single chat to the allowlist."""
        self.allowed_chat_ids.add(chat_id)

    def remove_chat(self, chat_id: int) -> None:
        """Remove a chat from the allowlist."""
        self.allowed_chat_ids.discard(chat_id)

    def update_allowed_chats(self, chat_ids: set[int]) -> None:
        self.allowed_chat_ids = chat_ids

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        # Always allow my_chat_member updates through so the bot can detect
        # being added to / removed from groups regardless of allowlist state.
        if isinstance(event, ChatMemberUpdated):
            return await handler(event, data)

        chat = data.get("event_chat")
        if chat is not None and chat.id not in self.allowed_chat_ids:
            logger.debug("Chat not in allowlist, dropping update", chat_id=chat.id)
            return None
        return await handler(event, data)
