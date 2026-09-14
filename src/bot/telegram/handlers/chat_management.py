"""
Chat management handlers — activation flow for new groups.

When the bot is added to a group, an approval request is sent to the admin
via inline keyboard.  The admin can activate or decline the group.
"""

from __future__ import annotations

from typing import Any

from aiogram import Bot, F, Router
from aiogram.enums import ChatMemberStatus, ChatType
from aiogram.types import (
    CallbackQuery,
    ChatMemberUpdated,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from bot.log import get_logger
from bot.telegram.filters.admin import IsAdminUser
from bot.telegram.middlewares.allowlist import ChatAllowlistMiddleware

logger = get_logger(__name__)

chat_management_router = Router(name="chat_management")

# Callback data prefixes
_CB_ACTIVATE = "chat_activate:"
_CB_DECLINE = "chat_decline:"


def setup_chat_management_router(admin_user_id: int) -> None:
    """Restrict callback-query handling to the admin user."""
    chat_management_router.callback_query.filter(IsAdminUser(admin_user_id))


# ---------------------------------------------------------------------------
# my_chat_member — bot was added to / removed from a group
# ---------------------------------------------------------------------------


@chat_management_router.my_chat_member(
    F.new_chat_member.status.in_({ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR}),
    F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}),
)
async def on_bot_added_to_group(
    event: ChatMemberUpdated,
    bot: Bot,
    settings: Any,
) -> None:
    """Send an activation request to the admin when the bot joins a group."""
    chat = event.chat
    added_by = event.from_user

    admin_chat_id = settings.admin_user_id
    if not admin_chat_id:
        logger.warning(
            "Bot added to group but no admin_user_id configured, cannot request approval",
            chat_id=chat.id,
        )
        return

    added_by_text = f"@{added_by.username}" if added_by.username else added_by.full_name

    text = (
        f"<b>Bot added to a new group</b>\n\n"
        f"<b>Group:</b> {chat.title or 'Untitled'}\n"
        f"<b>Chat ID:</b> <code>{chat.id}</code>\n"
        f"<b>Type:</b> {chat.type}\n"
        f"<b>Added by:</b> {added_by_text}\n\n"
        f"Activate this group?"
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="\u2705 Activate",
                    callback_data=f"{_CB_ACTIVATE}{chat.id}",
                ),
                InlineKeyboardButton(
                    text="\u274c Decline",
                    callback_data=f"{_CB_DECLINE}{chat.id}",
                ),
            ]
        ]
    )

    try:
        await bot.send_message(chat_id=admin_chat_id, text=text, reply_markup=keyboard)
        logger.info(
            "Sent group activation request to admin",
            chat_id=chat.id,
            admin_id=admin_chat_id,
        )
    except Exception:
        logger.exception("Failed to send activation request to admin", chat_id=chat.id)


@chat_management_router.my_chat_member(
    F.new_chat_member.status.in_({ChatMemberStatus.LEFT, ChatMemberStatus.KICKED}),
    F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}),
)
async def on_bot_removed_from_group(
    event: ChatMemberUpdated,
    allowlist: ChatAllowlistMiddleware | None = None,
    chat_repo: Any = None,
) -> None:
    """Clean up allowlist and deactivate chat when the bot is removed from a group."""
    chat_id = event.chat.id
    if allowlist is not None:
        allowlist.remove_chat(chat_id)
    if chat_repo is not None:
        try:
            await chat_repo.deactivate_chat(chat_id)
        except Exception:
            logger.exception("Failed to deactivate chat in database", chat_id=chat_id)
    logger.info("Bot removed from group, deactivated", chat_id=chat_id)


# ---------------------------------------------------------------------------
# Callback queries — admin presses Activate / Decline
# ---------------------------------------------------------------------------


@chat_management_router.callback_query(F.data.startswith(_CB_ACTIVATE))
async def on_activate_group(
    callback: CallbackQuery,
    bot: Bot,
    chat_repo: Any,
    allowlist: ChatAllowlistMiddleware | None = None,
) -> None:
    """Activate a group after admin approval."""
    if not callback.data:
        return

    chat_id = int(callback.data.removeprefix(_CB_ACTIVATE))

    # Register in database
    await chat_repo.upsert_chat(chat_id=chat_id)

    # Add to runtime allowlist
    if allowlist is not None:
        allowlist.add_chat(chat_id)

    # Try to fetch group title for a nicer confirmation
    title = f"<code>{chat_id}</code>"
    try:
        chat_info = await bot.get_chat(chat_id)
        if chat_info.title:
            title = f"<b>{chat_info.title}</b> ({chat_id})"
            # Update title in DB now that we know it
            await chat_repo.upsert_chat(chat_id=chat_id, title=chat_info.title)
    except Exception:
        pass

    await callback.message.edit_text(
        f"\u2705 Group {title} has been activated.",
    )
    await callback.answer("Group activated")
    logger.info("Admin activated group", chat_id=chat_id)


@chat_management_router.callback_query(F.data.startswith(_CB_DECLINE))
async def on_decline_group(
    callback: CallbackQuery,
    bot: Bot,
) -> None:
    """Decline a group and leave it."""
    if not callback.data:
        return

    chat_id = int(callback.data.removeprefix(_CB_DECLINE))

    # Leave the group
    try:
        await bot.leave_chat(chat_id)
    except Exception:
        logger.debug("Could not leave chat (maybe already left)", chat_id=chat_id)

    await callback.message.edit_text(
        f"\u274c Group <code>{chat_id}</code> declined. Bot has left the group.",
    )
    await callback.answer("Group declined")
    logger.info("Admin declined group, bot left", chat_id=chat_id)
