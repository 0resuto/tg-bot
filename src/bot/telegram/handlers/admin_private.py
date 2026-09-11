"""
Admin private chat handlers.
"""

from __future__ import annotations

from typing import Any

import structlog
from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from bot.config import Settings  # type: ignore
from bot.domain.models import ChatMessage, MemberIdentity
from bot.telegram.filters.admin import IsAdminChat, IsAdminUser

logger = structlog.get_logger(__name__)

admin_private_router = Router(name="admin_private")


def setup_admin_private_router(settings: Settings) -> None:
    admin_chat_id = settings.admin_chat_id or settings.admin_user_id
    admin_private_router.message.filter(
        IsAdminChat(admin_chat_id),
        IsAdminUser(settings.admin_user_id),
    )


@admin_private_router.message(Command("forget_fact"))
async def cmd_forget_fact(
    message: Message,
    command: CommandObject,
    memory_service: Any,
    chat_repo: Any,
) -> None:
    description = command.args
    if not description:
        await message.reply("Usage: /forget_fact <description>")
        return

    active_chats = await chat_repo.get_active_chat_ids()
    if not active_chats:
        await message.reply("No active group chats found.")
        return

    target_chat_id = active_chats[0]

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
    token_repo: Any,
    chat_repo: Any,
    member_repo: Any,
) -> None:
    active_chats = await chat_repo.get_active_chat_ids()
    if not active_chats:
        await message.reply("No active group chats found.")
        return

    target_chat_id = active_chats[0]

    try:
        mem_stats = await memory_service.get_stats(chat_id=target_chat_id)
        token_stats = await token_repo.get_usage_stats(chat_id=target_chat_id, days=30)
        members = await member_repo.get_members_by_chat(target_chat_id)
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
            f"- Last Ingestion: {last_ingestion_str}\n\n"
            "Token Usage (30 days):\n"
            f"- Today: {token_stats.get('today_tokens', 0)}\n"
            f"- This Week: {token_stats.get('week_tokens', 0)}\n"
            f"- This Month: {token_stats.get('month_tokens', 0)}"
        )
        await message.reply(reply_text)
    except Exception as e:
        logger.error("Failed to get memory stats", error=str(e))
        await message.reply("Failed to retrieve statistics due to an error.")


@admin_private_router.message(F.text, ~F.text.startswith("/"))
async def handle_admin_private_message(
    message: Message,
    member_repo: Any,
    context_builder: Any,
    response_service: Any,
    chat_repo: Any,
    settings: Settings,
) -> None:
    """Handle 1-on-1 private chat messages with the admin using shared group memory."""
    if not message.from_user or not message.text:
        return

    identity = MemberIdentity(
        telegram_user_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name,
    )

    # 1. Record incoming message in private context
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

    # 2. Determine target group chats for shared memory access
    active_chats = await chat_repo.get_active_chat_ids()
    group_chats = [cid for cid in active_chats if cid != message.chat.id]

    memory_chat_ids = [message.chat.id]
    target_group_id = None
    if group_chats:
        neg_groups = [cid for cid in group_chats if cid < 0]
        target_group_id = neg_groups[0] if neg_groups else group_chats[0]
        memory_chat_ids.append(target_group_id)

    # 3. Collect active user names for quick facts (admin + any group member mentioned)
    active_user_names = [identity.display_name]
    if target_group_id:
        try:
            members = await member_repo.get_members_by_chat(target_group_id)
            for m in members:
                if (
                    m.display_name
                    and m.display_name not in active_user_names
                    and (
                        m.display_name.lower() in message.text.lower()
                        or (m.username and m.username.lower() in message.text.lower())
                    )
                ):
                    active_user_names.append(m.display_name)
        except Exception as e:
            logger.debug("Failed to retrieve group members for private context", error=str(e))

    # 4. Generate response with shared memory access
    response = await response_service.generate_response(
        chat_id=message.chat.id,
        user_display_name=identity.display_name,
        active_user_names=active_user_names,
        memory_chat_ids=memory_chat_ids,
    )

    if response:
        sent_message = await message.reply(response)
        # Store bot response in private context
        bot_name = (
            settings.bot_names.split(",")[0].strip()
            if hasattr(settings, "bot_names") and settings.bot_names
            else "Bot"
        )
        bot_chat_msg = ChatMessage(
            chat_id=message.chat.id,
            user_id=message.bot.id if message.bot else 0,
            text=response,
            timestamp=sent_message.date,
            message_id=sent_message.message_id,
            display_name=bot_name,
            reply_to_message_id=message.message_id,
        )
        await context_builder.add_message(msg=bot_chat_msg)
