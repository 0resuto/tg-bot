from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.types import Chat, Message, User

from bot.config import Settings
from bot.models import MemberIdentity
from bot.telegram.filters import IsAdminUser
from bot.telegram.handlers.admin_private import (
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
    message.reply.assert_awaited_once_with("Алиса обожает флэт уайт!", parse_mode="HTML")

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

    message.reply.assert_awaited_once_with("Hello Admin!", parse_mode="HTML")
    assert context_builder.add_message.call_count == 2
    assert response_service.generate_response.call_args.kwargs["active_user_names"] == ["Admin"]
