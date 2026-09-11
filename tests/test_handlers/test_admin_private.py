from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.types import Chat, Message, User

from bot.config import Settings
from bot.domain.models import MemberIdentity
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
    class MockMemberRepo:
        async def get_members_by_chat(self, chat_id):
            return [
                MemberIdentity(telegram_user_id=2, username="alice", first_name="Алиса"),
                MemberIdentity(telegram_user_id=3, username="bob", first_name="Боб"),
            ]

    # Chat repo mock
    class MockChatRepo:
        async def get_active_chat_ids(self):
            return [111, -100123456]

    # Response service mock
    generate_calls = []

    class MockResponseService:
        async def generate_response(
            self, chat_id, user_display_name, active_user_names, *, memory_chat_ids=None
        ):
            generate_calls.append(
                {
                    "chat_id": chat_id,
                    "user_display_name": user_display_name,
                    "active_user_names": active_user_names,
                    "memory_chat_ids": memory_chat_ids,
                }
            )
            return "Алиса обожает флэт уайт!"

    settings = Settings(admin_user_id=111, admin_chat_id=111, bot_names="Ista")

    # Run handler
    await handle_admin_private_message(
        message=message,
        member_repo=MockMemberRepo(),
        context_builder=MockContextBuilder(),
        response_service=MockResponseService(),
        chat_repo=MockChatRepo(),
        settings=settings,
    )

    # Verify message.reply was called with bot response
    message.reply.assert_awaited_once_with("Алиса обожает флэт уайт!")

    # Verify ResponseService received private chat_id and memory_chat_ids with group chat
    assert len(generate_calls) == 1
    call = generate_calls[0]
    assert call["chat_id"] == 111
    assert call["user_display_name"] == "Admin"
    assert "Алиса" in call["active_user_names"]  # Alice was detected in text
    assert call["memory_chat_ids"] == [111, -100123456]  # Included group chat for shared memory

    # Verify both incoming user message and bot response were saved in private context
    assert len(added_messages) == 2
    assert added_messages[0].text == "Что любит Алиса?"
    assert added_messages[0].display_name == "Admin"
    assert added_messages[1].text == "Алиса обожает флэт уайт!"
    assert added_messages[1].display_name == "Ista"
