"""
Mention filter using MentionDetector.
"""

from __future__ import annotations

from typing import Any

from aiogram import Bot
from aiogram.filters import Filter
from aiogram.types import Message


class IsBotMentioned(Filter):
    async def __call__(self, message: Message, mention_detector: Any, bot: Bot) -> bool:
        reply_to_user_id = None
        if message.reply_to_message and message.reply_to_message.from_user:
            reply_to_user_id = message.reply_to_message.from_user.id

        return mention_detector.is_addressed(
            text=message.text or getattr(message, "caption", None) or "",
            entities=message.entities or getattr(message, "caption_entities", None),
            reply_to_user_id=reply_to_user_id,
        )
