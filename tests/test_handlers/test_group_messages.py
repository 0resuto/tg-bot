"""Tests for group message handler."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.types import Chat, Message, MessageEntity, User

from bot.domain.models import ChatMessage
from bot.telegram.handlers.group_messages import handle_group_message


@pytest.mark.asyncio
async def test_handle_group_message_with_text():
    """Verify standard text message processing in group chats."""
    user = User(id=123, is_bot=False, first_name="Alice", username="alice123")
    chat = Chat(id=-100111222, type="supergroup", title="Test Group")

    message = MagicMock(spec=Message)
    message.message_id = 42
    message.from_user = user
    message.chat = chat
    message.text = "Hello everyone"
    message.caption = None
    message.date = datetime.now(UTC)
    message.reply_to_message = None
    message.entities = None
    message.caption_entities = None

    member_repo = MagicMock()
    member_repo.upsert_member = AsyncMock()

    context_builder = MagicMock()
    context_builder.add_message = AsyncMock()
    context_builder.get_context = AsyncMock(return_value=[])

    debouncer = MagicMock()
    debouncer.on_message = AsyncMock()

    mention_detector = MagicMock()
    mention_detector.is_addressed = MagicMock(return_value=False)

    response_service = MagicMock()
    response_service.generate_response = AsyncMock()

    await handle_group_message(
        message=message,
        member_repo=member_repo,
        context_builder=context_builder,
        debouncer=debouncer,
        mention_detector=mention_detector,
        response_service=response_service,
    )

    # Verify member and message recording
    member_repo.upsert_member.assert_awaited_once()
    context_builder.add_message.assert_awaited_once()
    saved_msg: ChatMessage = context_builder.add_message.call_args[1]["msg"]
    assert saved_msg.text == "Hello everyone"
    assert saved_msg.user_id == 123
    assert saved_msg.chat_id == -100111222

    debouncer.on_message.assert_awaited_once_with(message=saved_msg)
    mention_detector.is_addressed.assert_called_once_with(
        text="Hello everyone",
        entities=None,
        reply_to_user_id=None,
    )
    response_service.generate_response.assert_not_called()


@pytest.mark.asyncio
async def test_handle_group_message_with_caption_and_mention():
    """Verify photo/document message with caption and mention triggers response."""
    user = User(id=456, is_bot=False, first_name="Bob", username="bob456")
    chat = Chat(id=-100111222, type="supergroup", title="Test Group")

    bot_user = User(id=999, is_bot=True, first_name="TestBot", username="test_bot")
    bot_reply_msg = MagicMock(spec=Message)
    bot_reply_msg.message_id = 99
    bot_reply_msg.date = datetime.now(UTC)
    bot_reply_msg.from_user = bot_user
    bot_reply_msg.text = "I see your chart!"

    message = MagicMock(spec=Message)
    message.message_id = 43
    message.from_user = user
    message.chat = chat
    message.text = None
    message.caption = "@test_bot what is this?"
    message.date = datetime.now(UTC)
    message.reply_to_message = None
    message.entities = None
    mention_entity = MessageEntity(type="mention", offset=0, length=9)
    message.caption_entities = [mention_entity]
    message.reply = AsyncMock(return_value=bot_reply_msg)

    member_repo = MagicMock()
    member_repo.upsert_member = AsyncMock()

    context_builder = MagicMock()
    context_builder.add_message = AsyncMock()
    context_builder.get_context = AsyncMock(return_value=[])

    debouncer = MagicMock()
    debouncer.on_message = AsyncMock()

    mention_detector = MagicMock()
    mention_detector.is_addressed = MagicMock(return_value=True)

    response_service = MagicMock()
    response_service.generate_response = AsyncMock(return_value="I see your chart!")

    await handle_group_message(
        message=message,
        member_repo=member_repo,
        context_builder=context_builder,
        debouncer=debouncer,
        mention_detector=mention_detector,
        response_service=response_service,
    )

    # Verify caption was used as message text
    assert context_builder.add_message.call_count == 2  # user msg + bot response
    user_msg: ChatMessage = context_builder.add_message.call_args_list[0][1]["msg"]
    assert user_msg.text == "@test_bot what is this?"

    debouncer.on_message.assert_awaited_once_with(message=user_msg)
    mention_detector.is_addressed.assert_called_once_with(
        text="@test_bot what is this?",
        entities=[mention_entity],
        reply_to_user_id=None,
    )

    message.reply.assert_awaited_once_with("I see your chart!")
    bot_msg: ChatMessage = context_builder.add_message.call_args_list[1][1]["msg"]
    assert bot_msg.text == "I see your chart!"
    assert bot_msg.user_id == 999
