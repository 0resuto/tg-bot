"""
Group messages handler.
"""

from __future__ import annotations

from typing import Any

from aiogram import F, Router
from aiogram.enums import ChatType as EnumChatType
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import Message

from bot.config import Settings
from bot.log import get_logger
from bot.models import ChatMessage, MemberIdentity
from bot.telegram.filters import IsGroupChat
from bot.telegram.media import extract_message_content

logger = get_logger(__name__)


async def safe_reply(message: Message, text: str) -> Message | None:
    """Safely reply to a message with fallbacks for HTML parsing and deleted messages."""
    try:
        return await message.reply(text)
    except TelegramBadRequest as exc:
        err = str(exc).lower()
        if "reply message not found" in err:
            try:
                return await message.answer(text)
            except TelegramBadRequest as inner_exc:
                if "can't parse entities" in str(inner_exc).lower():
                    return await message.answer(text, parse_mode=None)
                raise
        elif "can't parse entities" in err or "entity" in err:
            try:
                return await message.reply(text, parse_mode=None)
            except TelegramBadRequest as inner_exc:
                if "reply message not found" in str(inner_exc).lower():
                    return await message.answer(text, parse_mode=None)
                raise
        raise
    except TelegramForbiddenError as exc:
        logger.warning("Cannot send message: bot was blocked or kicked", error=str(exc))
        return None


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
    settings: Settings | None = None,
) -> None:
    if not message.from_user:
        return

    text = extract_message_content(message)
    if not text:
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
    is_addressed = mention_detector.is_addressed(
        text=raw_text,
        entities=entities,
        reply_to_user_id=reply_to_user_id,
    )

    if is_addressed:
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
            sent_msg = await safe_reply(message, response)
            if sent_msg is not None:
                bot_from_user = getattr(sent_msg, "from_user", None)
                bot_user_id = (
                    bot_from_user.id if bot_from_user else (message.bot.id if message.bot else 0)
                )
                bot_name = (
                    bot_from_user.first_name
                    if bot_from_user and bot_from_user.first_name
                    else "Bot"
                )
                bot_msg = ChatMessage(
                    chat_id=message.chat.id,
                    user_id=bot_user_id,
                    text=getattr(sent_msg, "text", None) or response,
                    timestamp=sent_msg.date,
                    message_id=sent_msg.message_id,
                    display_name=bot_name,
                    reply_to_message_id=message.message_id,
                )
                await context_builder.add_message(msg=bot_msg)
