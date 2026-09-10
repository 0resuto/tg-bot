"""
Allowlist middleware.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import structlog
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

logger = structlog.get_logger(__name__)


class ChatAllowlistMiddleware(BaseMiddleware):
    def __init__(self, allowed_chat_ids: set[int]):
        self.allowed_chat_ids = allowed_chat_ids

    def update_allowed_chats(self, chat_ids: set[int]) -> None:
        self.allowed_chat_ids = chat_ids

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        chat = data.get("event_chat")
        if chat is not None and chat.id not in self.allowed_chat_ids:
            logger.debug("Chat not in allowlist, dropping update", chat_id=chat.id)
            return None
        return await handler(event, data)
