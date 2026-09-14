"""
Group messages handler.
"""

from __future__ import annotations

from typing import Any

from aiogram import F, Router
from aiogram.enums import ChatType as EnumChatType
from aiogram.types import Message

from bot.config import Settings
from bot.domain.models import ChatMessage, MemberIdentity
from bot.log import get_logger
from bot.telegram.filters.admin import IsGroupChat
from bot.telegram.media import extract_message_content

logger = get_logger(__name__)

group_messages_router = Router(name="group_messages")


def setup_group_messages_router(settings: Settings) -> None:
    if group_messages_router.message._handler.filters:
        group_messages_router.message._handler.filters.clear()
    group_messages_router.message.filter(
        F.chat.type.in_({EnumChatType.GROUP, EnumChatType.SUPERGROUP}),
        IsGroupChat(settings.group_chat_id),
    )


@group_messages_router.message()
async def handle_group_message(
    message: Message,
    member_repo: Any,
    context_builder: Any,
    debouncer: Any,
    mention_detector: Any,
    response_service: Any,
) -> None:
    text = extract_message_content(message)
    if not message.from_user or not text:
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
        text=text,
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

    raw_text = message.text or message.caption or ""
    entities = message.entities or message.caption_entities
    is_mentioned = mention_detector.is_addressed(
        text=raw_text,
        entities=entities,
        reply_to_user_id=reply_to_user_id,
    )

    if is_mentioned:
        recent_context = await context_builder.get_context(chat_id=message.chat.id)
        active_user_names = list({msg.display_name for msg in recent_context if msg.display_name})
        bot_id = message.bot.id if message.bot else 0
        response = await response_service.generate_response(
            chat_id=message.chat.id,
            user_display_name=identity.display_name,
            active_user_names=active_user_names,
            bot_id=bot_id,
        )
        if response:
            sent_msg = await message.reply(response)
            bot_date = getattr(sent_msg, "date", None) or message.date
            bot_msg_id = getattr(sent_msg, "message_id", 0)
            bot_from_user = getattr(sent_msg, "from_user", None)
            bot_user_id = (
                bot_from_user.id if bot_from_user else (message.bot.id if message.bot else 0)
            )
            bot_name = (
                bot_from_user.first_name if bot_from_user and bot_from_user.first_name else "Bot"
            )
            bot_msg = ChatMessage(
                chat_id=message.chat.id,
                user_id=bot_user_id,
                text=getattr(sent_msg, "text", None) or response,
                timestamp=bot_date,
                message_id=bot_msg_id,
                display_name=bot_name,
                reply_to_message_id=message.message_id,
            )
            await context_builder.add_message(msg=bot_msg)
