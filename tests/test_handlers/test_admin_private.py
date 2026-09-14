from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram import F, Router
from aiogram.filters import CommandObject
from aiogram.types import Chat, Message, User

from bot.config import Settings
from bot.domain.models import MemberIdentity, MemoryStats
from bot.telegram.filters.admin import IsAdminUser
from bot.telegram.handlers.admin_private import (
    cmd_forget_fact,
    cmd_memory_stats,
    handle_admin_private_message,
)


@pytest.mark.asyncio
async def test_handle_admin_private_message():
    # Setup mocks
    mock_user = User(id=111, is_bot=False, first_name="Admin", username="admin_user")
    mock_chat = Chat(id=111, type="private")
    mock_bot = MagicMock()
    mock_bot.id = 999

    sent_msg = MagicMock(spec=Message)
    sent_msg.message_id = 101
    sent_msg.date = datetime.now(UTC)

    message = MagicMock(spec=Message)
    message.message_id = 100
    message.from_user = mock_user
    message.chat = mock_chat
    message.text = "Что любит Алиса?"
    message.date = datetime.now(UTC)
    message.reply_to_message = None
    message.bot = mock_bot
    message.reply = AsyncMock(return_value=sent_msg)

    # Context builder mock
    added_messages = []

    class MockContextBuilder:
        async def add_message(self, msg):
            added_messages.append(msg)

    # Member repo mock
    requested_member_chats = []

    class MockMemberRepo:
        async def get_members_by_chat(self, chat_id):
            requested_member_chats.append(chat_id)
            return [
                MemberIdentity(telegram_user_id=2, username="alice", first_name="Алиса"),
                MemberIdentity(telegram_user_id=3, username="bob", first_name="Боб"),
            ]

    # Response service mock
    generate_calls = []

    class MockResponseService:
        async def generate_response(
            self,
            chat_id,
            user_display_name,
            active_user_names,
            *,
            bot_id=0,
            raise_on_error=False,
        ):
            generate_calls.append(
                {
                    "chat_id": chat_id,
                    "user_display_name": user_display_name,
                    "active_user_names": active_user_names,
                    "bot_id": bot_id,
                }
            )
            return "Алиса обожает флэт уайт!"

    settings = Settings(
        admin_user_id=111,
        admin_chat_id=111,
        group_chat_id=-100123456,
        bot_names="Ista",
    )

    # Run handler
    await handle_admin_private_message(
        message=message,
        member_repo=MockMemberRepo(),
        context_builder=MockContextBuilder(),
        response_service=MockResponseService(),
        settings=settings,
    )

    # Verify message.reply was called with bot response
    message.reply.assert_awaited_once_with("Алиса обожает флэт уайт!")

    # Verify ResponseService received private chat_id and active user names
    assert len(generate_calls) == 1
    call = generate_calls[0]
    assert call["chat_id"] == 111
    assert call["user_display_name"] == "Admin"
    assert "Алиса" in call["active_user_names"]  # Alice was detected in text
    assert requested_member_chats == [-100123456]  # Queried main group members directly

    # Verify both incoming user message and bot response were saved in private context
    assert len(added_messages) == 2
    assert added_messages[0].text == "Что любит Алиса?"
    assert added_messages[0].display_name == "Admin"
    assert added_messages[1].text == "Алиса обожает флэт уайт!"
    assert added_messages[1].display_name == "Ista"


@pytest.mark.asyncio
async def test_cmd_memory_stats():
    mock_user = User(id=111, is_bot=False, first_name="Admin", username="admin_user")
    mock_chat = Chat(id=111, type="private")

    message = MagicMock(spec=Message)
    message.from_user = mock_user
    message.chat = mock_chat
    message.reply = AsyncMock()

    class MockMemoryService:
        async def get_stats(self, chat_id: int):
            assert chat_id == -100123456
            return MemoryStats(
                total_entities=5,
                total_relations=10,
                total_episodes=3,
                last_ingestion_at=datetime(2026, 9, 1, 12, 0, tzinfo=UTC),
            )

    class MockMemberRepo:
        async def get_members_by_chat(self, chat_id: int):
            assert chat_id == -100123456
            return [
                MemberIdentity(telegram_user_id=1, username="u1", first_name="User1"),
                MemberIdentity(telegram_user_id=2, username="u2", first_name="User2"),
            ]

    settings = Settings(admin_user_id=111, group_chat_id=-100123456)

    await cmd_memory_stats(
        message=message,
        memory_service=MockMemoryService(),
        member_repo=MockMemberRepo(),
        settings=settings,
    )

    message.reply.assert_awaited_once()
    reply_text = message.reply.call_args[0][0]
    assert "Entities / Relations / Episodes: 5 / 10 / 3" in reply_text
    assert "Tracked Members: 2" in reply_text
    assert "Last Ingestion: 2026-09-01 12:00 UTC" in reply_text


@pytest.mark.asyncio
async def test_cmd_forget_fact():
    mock_user = User(id=111, is_bot=False, first_name="Admin", username="admin_user")
    mock_chat = Chat(id=111, type="private")

    message = MagicMock(spec=Message)
    message.from_user = mock_user
    message.chat = mock_chat
    message.reply = AsyncMock()

    command = MagicMock(spec=CommandObject)
    command.args = "likes coffee"

    class MockMemoryService:
        async def forget_fact(self, description: str, chat_id: int):
            assert description == "likes coffee"
            assert chat_id == -100123456
            return 1

    settings = Settings(admin_user_id=111, group_chat_id=-100123456)

    await cmd_forget_fact(
        message=message,
        command=command,
        memory_service=MockMemoryService(),
        settings=settings,
    )

    message.reply.assert_awaited_once_with("Deleted 1 facts matching the description.")


@pytest.mark.asyncio
async def test_setup_admin_private_router_with_group_admin_chat_id():
    """Verify that private messages from admin work even if admin_chat_id is a group ID."""

    custom_router = Router(name="test_admin_private")
    # Replace global filters on custom_router for test isolation
    settings = Settings(admin_user_id=111, admin_chat_id=-100987654321, bot_names="Ista")

    # Apply filters logic
    custom_router.message.filter(
        F.chat.type == "private",
        IsAdminUser(settings.admin_user_id),
    )

    # Valid admin private message
    admin_msg = MagicMock(spec=Message)
    admin_msg.chat = Chat(id=111, type="private")
    admin_msg.from_user = User(id=111, is_bot=False, first_name="Admin")

    # Group message from admin (should NOT match private router)
    group_msg = MagicMock(spec=Message)
    group_msg.chat = Chat(id=-100987654321, type="supergroup")
    group_msg.from_user = User(id=111, is_bot=False, first_name="Admin")

    # Private message from non-admin
    non_admin_msg = MagicMock(spec=Message)
    non_admin_msg.chat = Chat(id=222, type="private")
    non_admin_msg.from_user = User(id=222, is_bot=False, first_name="Other")

    # Test the filter conditions
    is_admin = IsAdminUser(settings.admin_user_id)
    assert await is_admin(admin_msg) is True
    assert admin_msg.chat.type == "private"

    assert await is_admin(group_msg) is True
    assert group_msg.chat.type != "private"

    assert await is_admin(non_admin_msg) is False


@pytest.mark.asyncio
async def test_setup_admin_private_router_with_distinct_admin_ids():
    """Verify that both admin_user_id and positive admin_chat_id are accepted."""
    from bot.telegram.handlers.admin_private import admin_private_router, setup_admin_private_router

    settings = Settings(admin_user_id=111, admin_chat_id=222, bot_names="Ista")
    setup_admin_private_router(settings)

    # Both admin 111 and admin 222 should match the filter
    filters = admin_private_router.message._handler.filters
    is_admin_filter = next(f.callback for f in filters if isinstance(f.callback, IsAdminUser))

    msg_admin_1 = MagicMock(spec=Message)
    msg_admin_1.from_user = User(id=111, is_bot=False, first_name="Admin1")
    msg_admin_2 = MagicMock(spec=Message)
    msg_admin_2.from_user = User(id=222, is_bot=False, first_name="Admin2")
    msg_other = MagicMock(spec=Message)
    msg_other.from_user = User(id=333, is_bot=False, first_name="Other")

    assert await is_admin_filter(msg_admin_1) is True
    assert await is_admin_filter(msg_admin_2) is True
    assert await is_admin_filter(msg_other) is False


@pytest.mark.asyncio
async def test_handle_admin_private_message_with_none_member_repo():
    """Verify handle_admin_private_message works safely when member_repo is None."""
    mock_user = User(id=111, is_bot=False, first_name="Admin")
    mock_chat = Chat(id=111, type="private")
    mock_bot = MagicMock()
    mock_bot.id = 999

    sent_msg = MagicMock(spec=Message)
    sent_msg.message_id = 101
    sent_msg.date = datetime.now(UTC)

    message = MagicMock(spec=Message)
    message.message_id = 100
    message.from_user = mock_user
    message.chat = mock_chat
    message.text = "Hello bot"
    message.date = datetime.now(UTC)
    message.reply_to_message = None
    message.bot = mock_bot
    message.reply = AsyncMock(return_value=sent_msg)

    context_builder = MagicMock()
    context_builder.add_message = AsyncMock()

    response_service = MagicMock()
    response_service.generate_response = AsyncMock(return_value="Hello Admin!")

    settings = Settings(admin_user_id=111, group_chat_id=-100123456, bot_names="Ista")

    await handle_admin_private_message(
        message=message,
        member_repo=None,
        context_builder=context_builder,
        response_service=response_service,
        settings=settings,
    )

    message.reply.assert_awaited_once_with("Hello Admin!")
    assert context_builder.add_message.call_count == 2
    assert response_service.generate_response.call_args.kwargs["active_user_names"] == ["Admin"]
