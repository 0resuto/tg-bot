"""
Admin private chat handlers.
"""

from __future__ import annotations

from typing import Any

import structlog
from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from bot.config import Settings  # type: ignore
from bot.telegram.filters.admin import IsAdminChat, IsAdminUser

logger = structlog.get_logger(__name__)

admin_private_router = Router(name="admin_private")


def setup_admin_private_router(settings: Settings) -> None:
    admin_private_router.message.filter(
        IsAdminChat(settings.admin_chat_id),
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
) -> None:
    active_chats = await chat_repo.get_active_chat_ids()
    if not active_chats:
        await message.reply("No active group chats found.")
        return

    target_chat_id = active_chats[0]

    try:
        mem_stats = await memory_service.get_stats(chat_id=target_chat_id)
        token_stats = await token_repo.get_usage_stats(chat_id=target_chat_id, days=30)

        reply_text = (
            "Memory Stats:\n"
            f"- Facts/Entities/Relations: {mem_stats.get('facts', 0)} / {mem_stats.get('entities', 0)} / {mem_stats.get('relations', 0)}\n"
            f"- Tracked Members: {mem_stats.get('tracked_members', 0)}\n"
            f"- Last Ingestion: {mem_stats.get('last_ingestion', 'Never')}\n\n"
            "Token Usage (30 days):\n"
            f"- Today: {token_stats.get('today', 0)}\n"
            f"- This Week: {token_stats.get('this_week', 0)}\n"
            f"- This Month: {token_stats.get('this_month', 0)}"
        )
        await message.reply(reply_text)
    except Exception as e:
        logger.error("Failed to get memory stats", error=str(e))
        await message.reply("Failed to retrieve statistics due to an error.")
