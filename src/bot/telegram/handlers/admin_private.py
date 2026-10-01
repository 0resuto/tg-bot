"""
Admin private chat handlers.
"""

from __future__ import annotations

import re
from typing import Any

from aiogram import F, Router
from aiogram.types import Message

from bot.config import Settings
from bot.log import get_logger
from bot.models import ChatMessage, MemberIdentity
from bot.telegram.filters import IsAdminUser
from bot.telegram.handlers.group_messages import safe_reply
from bot.telegram.media import extract_message_content

logger = get_logger(__name__)

admin_private_router = Router(name="admin_private")


def setup_admin_private_router(settings: Settings) -> None:
    admin_ids = {uid for uid in (settings.admin_user_id, settings.admin_chat_id) if uid > 0}
    if admin_private_router.message._handler.filters:
        admin_private_router.message._handler.filters.clear()
    admin_private_router.message.filter(
        F.chat.type == "private",
        IsAdminUser(admin_ids),
    )


@admin_private_router.message()
async def handle_admin_private_message(
    message: Message,
    member_repo: Any,
    context_builder: Any,
    response_service: Any,
    settings: Settings,
) -> None:
    """Handle 1-on-1 private chat messages with the admin using shared group memory."""
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

    # 1. Update context with incoming user message
    user_chat_msg = ChatMessage(
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
    await context_builder.add_message(msg=user_chat_msg)

    # 2. Extract active participant names for context
    active_user_names = [identity.display_name]
    target_chat_id = settings.group_chat_id
    if target_chat_id and target_chat_id != 0:
        try:
            members = await member_repo.get_members_by_chat(target_chat_id)
            for m in members:
                names_to_check = [m.display_name]
                if m.first_name:
                    names_to_check.append(m.first_name)
                if m.username:
                    names_to_check.append(m.username)
                    names_to_check.append(f"@{m.username}")

                matched = any(
                    name and re.search(rf"\b{re.escape(name)}\b", text, re.IGNORECASE)
                    for name in names_to_check
                )
                if matched and m.display_name not in active_user_names:
                    active_user_names.append(m.display_name)
        except Exception as exc:
            logger.warning("Failed to fetch group members for admin context", error=str(exc))

    # 3. Generate response with read-only access to group long-term memory
    bot_id = message.bot.id if message.bot else 0
    response = await response_service.generate_response(
        chat_id=message.chat.id,
        user_display_name=identity.display_name,
        active_user_names=active_user_names,
        bot_id=bot_id,
    )

    if response:
        sent_message = await safe_reply(message, response)
        if sent_message is not None:
            # Store bot response in private context
            bot_name = settings.bot_name_list[0] if settings.bot_name_list else "Bot"
            bot_chat_msg = ChatMessage(
                chat_id=message.chat.id,
                user_id=message.bot.id if message.bot else 0,
                text=getattr(sent_message, "text", None) or response,
                timestamp=sent_message.date,
                message_id=sent_message.message_id,
                display_name=bot_name,
                reply_to_message_id=message.message_id,
            )
            await context_builder.add_message(msg=bot_chat_msg)
