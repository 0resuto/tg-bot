"""
Admin private chat handlers.
"""

from __future__ import annotations

from typing import Any

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from bot.config import Settings
from bot.domain.models import ChatMessage, MemberIdentity
from bot.log import get_logger
from bot.telegram.filters.admin import IsAdminUser
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


@admin_private_router.message(Command("forget_fact"))
async def cmd_forget_fact(
    message: Message,
    command: CommandObject,
    memory_service: Any,
    settings: Settings,
) -> None:
    description = command.args
    if not description:
        await message.reply("Usage: /forget_fact <description>")
        return

    target_chat_id = settings.group_chat_id
    if not target_chat_id:
        await message.reply("GROUP_CHAT_ID is not configured.")
        return

    try:
        deleted_count = await memory_service.forget_fact(description, chat_id=target_chat_id)
        await message.reply(f"Deleted {deleted_count} facts matching the description.")
    except Exception as e:
        logger.error("Failed to forget fact", error=str(e))
        await message.reply("Failed to forget fact due to an error.")


@admin_private_router.message(Command("memory_stats"))
async def cmd_memory_stats(
    message: Message,
    memory_service: Any,
    member_repo: Any,
    settings: Settings,
) -> None:
    target_chat_id = settings.group_chat_id
    if not target_chat_id:
        await message.reply("GROUP_CHAT_ID is not configured.")
        return

    try:
        mem_stats = await memory_service.get_stats(chat_id=target_chat_id)
        members = await member_repo.get_members_by_chat(target_chat_id) if member_repo else []
        tracked_count = len(members)

        last_ingestion_str = (
            mem_stats.last_ingestion_at.strftime("%Y-%m-%d %H:%M UTC")
            if mem_stats.last_ingestion_at
            else "Never"
        )

        reply_text = (
            "Memory Stats:\n"
            f"- Entities / Relations / Episodes: {mem_stats.total_entities} / {mem_stats.total_relations} / {mem_stats.total_episodes}\n"
            f"- Tracked Members: {tracked_count}\n"
            f"- Last Ingestion: {last_ingestion_str}"
        )
        await message.reply(reply_text)
    except Exception as e:
        logger.error("Failed to get memory stats", error=str(e))
        await message.reply("Failed to retrieve statistics due to an error.")


@admin_private_router.message(~F.text.startswith("/"))
async def handle_admin_private_message(
    message: Message,
    member_repo: Any,
    context_builder: Any,
    response_service: Any,
    settings: Settings,
) -> None:
    """Handle 1-on-1 private chat messages with the admin using shared group memory."""
    text = extract_message_content(message, language=settings.bot_language)
    if not message.from_user or not text:
        return

    identity = MemberIdentity(
        telegram_user_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name,
    )

    # 1. Record incoming message in private context (never ingested into long-term memory)
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

    # 2. Collect active user names for quick facts (admin + any group member mentioned)
    active_user_names = [identity.display_name]
    target_group_id = settings.group_chat_id
    if target_group_id and member_repo:
        try:
            members = await member_repo.get_members_by_chat(target_group_id)
            for m in members:
                if (
                    m.display_name
                    and m.display_name not in active_user_names
                    and (
                        m.display_name.lower() in text.lower()
                        or (m.username and m.username.lower() in text.lower())
                    )
                ):
                    active_user_names.append(m.display_name)
        except Exception as e:
            logger.debug("Failed to retrieve group members for private context", error=str(e))

    # 3. Generate response with read-only access to group long-term memory
    bot_id = message.bot.id if message.bot else 0
    response = await response_service.generate_response(
        chat_id=message.chat.id,
        user_display_name=identity.display_name,
        active_user_names=active_user_names,
        bot_id=bot_id,
    )

    if response:
        sent_message = await message.reply(response)
        # Store bot response in private context
        bot_name = settings.bot_name_list[0] if settings.bot_name_list else "Bot"
        msg_date = getattr(sent_message, "date", None) or message.date
        msg_id = getattr(sent_message, "message_id", 0)
        bot_chat_msg = ChatMessage(
            chat_id=message.chat.id,
            user_id=message.bot.id if message.bot else 0,
            text=response,
            timestamp=msg_date,
            message_id=msg_id,
            display_name=bot_name,
            reply_to_message_id=message.message_id,
        )
        await context_builder.add_message(msg=bot_chat_msg)
