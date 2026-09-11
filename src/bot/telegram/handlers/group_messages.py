"""
Group messages handler.
"""

from __future__ import annotations

from typing import Any

import structlog
from aiogram import F, Router
from aiogram.enums import ChatType as EnumChatType
from aiogram.types import Message

from bot.domain.models import ChatMessage, MemberIdentity  # type: ignore

logger = structlog.get_logger(__name__)

group_messages_router = Router(name="group_messages")


@group_messages_router.message(
    F.chat.type.in_({EnumChatType.GROUP, EnumChatType.SUPERGROUP}), F.text
)
async def handle_group_message(
    message: Message,
    member_repo: Any,
    context_builder: Any,
    debouncer: Any,
    mention_detector: Any,
    response_service: Any,
) -> None:
    if not message.from_user or not message.text:
        return

    identity = MemberIdentity(
        telegram_user_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name,
    )
    await member_repo.upsert_member(
        chat_id=message.chat.id, member=identity, chat_title=message.chat.title
    )

    chat_msg = ChatMessage(
        chat_id=message.chat.id,
        user_id=message.from_user.id,
        text=message.text,
        timestamp=message.date,
        message_id=message.message_id,
        display_name=identity.display_name,
        reply_to_message_id=message.reply_to_message.message_id
        if message.reply_to_message
        else None,
    )
    await context_builder.add_message(msg=chat_msg)
    await debouncer.on_message(message=chat_msg)

    reply_to_user_id = None
    if message.reply_to_message and message.reply_to_message.from_user:
        reply_to_user_id = message.reply_to_message.from_user.id

    is_mentioned = mention_detector.is_addressed(
        text=message.text,
        entities=message.entities,
        reply_to_user_id=reply_to_user_id,
    )

    if is_mentioned:
        recent_context = await context_builder.get_context(chat_id=message.chat.id)
        active_user_names = list({msg.display_name for msg in recent_context if msg.display_name})

        response = await response_service.generate_response(
            chat_id=message.chat.id,
            user_display_name=identity.display_name,
            active_user_names=active_user_names,
        )
        if response:
            sent_msg = await message.reply(response)
            bot_msg = ChatMessage(
                chat_id=message.chat.id,
                user_id=sent_msg.from_user.id if sent_msg.from_user else 0,
                text=sent_msg.text or response,
                timestamp=sent_msg.date,
                message_id=sent_msg.message_id,
                display_name=sent_msg.from_user.first_name if sent_msg.from_user else "Bot",
                reply_to_message_id=message.message_id,
            )
            await context_builder.add_message(msg=bot_msg)
