"""Tests for group message handler."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.enums import ChatType as EnumChatType
from aiogram.types import Chat, Message, MessageEntity, User

from bot.config import Settings
from bot.domain.models import ChatMessage
from bot.telegram.filters.admin import IsGroupChat
from bot.telegram.handlers.group_messages import (
    handle_group_message,
    setup_group_messages_router,
)


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


@pytest.mark.asyncio
async def test_setup_group_messages_router_filters():
    """Verify group message router strictly filters by group_chat_id and group type."""
    settings = Settings(group_chat_id=-100111222)
    setup_group_messages_router(settings)

    valid_group_msg = MagicMock(spec=Message)
    valid_group_msg.chat = Chat(id=-100111222, type="supergroup")

    wrong_group_msg = MagicMock(spec=Message)
    wrong_group_msg.chat = Chat(id=-100999888, type="supergroup")

    private_msg = MagicMock(spec=Message)
    private_msg.chat = Chat(id=123, type="private")

    is_group = IsGroupChat(settings.group_chat_id)
    assert await is_group(valid_group_msg) is True
    assert valid_group_msg.chat.type in {EnumChatType.GROUP, EnumChatType.SUPERGROUP}

    assert await is_group(wrong_group_msg) is False
    assert await is_group(private_msg) is False


@pytest.mark.asyncio
async def test_dual_chat_dispatcher_routing_and_rejection(fake_redis):
    """Verify that messages from unauthorized groups/users are rejected at earliest filter level."""
    from aiogram import Bot
    from aiogram.types import Update

    from bot.telegram.dispatcher import create_dispatcher

    settings = Settings(
        group_chat_id=-100111222,
        admin_user_id=111,
        admin_chat_id=111,
    )

    mock_member_repo = MagicMock()
    mock_member_repo.upsert_member = AsyncMock()
    mock_member_repo.get_members_by_chat = AsyncMock(return_value=[])

    mock_context_builder = MagicMock()
    mock_context_builder.add_message = AsyncMock()
    mock_context_builder.get_context = AsyncMock(return_value=[])

    mock_debouncer = MagicMock()
    mock_debouncer.on_message = AsyncMock()

    mock_mention_detector = MagicMock()
    mock_mention_detector.is_addressed = MagicMock(return_value=False)

    mock_response_service = MagicMock()
    mock_response_service.generate_response = AsyncMock(return_value="Reply")

    mock_memory_service = MagicMock()

    services = {
        "member_repo": mock_member_repo,
        "context_builder": mock_context_builder,
        "debouncer": mock_debouncer,
        "mention_detector": mock_mention_detector,
        "response_service": mock_response_service,
        "memory_service": mock_memory_service,
        "settings": settings,
    }

    dp = create_dispatcher(settings, services, fake_redis)
    bot = MagicMock(spec=Bot)
    bot.id = 999
    now = datetime.now(UTC)

    # 1. Message from unauthorized group (-100999888) -> rejected at earliest filter level
    unauth_group_msg = Message(
        message_id=1,
        date=now,
        chat=Chat(id=-100999888, type="supergroup"),
        from_user=User(id=2, is_bot=False, first_name="Stranger"),
        text="Hello unauthorized group",
    )
    await dp.feed_update(bot, Update(update_id=1, message=unauth_group_msg))

    # 2. Message from unauthorized private user (999) -> rejected at earliest filter level
    unauth_private_msg = Message(
        message_id=2,
        date=now,
        chat=Chat(id=999, type="private"),
        from_user=User(id=999, is_bot=False, first_name="Stranger"),
        text="Hello unauthorized private",
    )
    await dp.feed_update(bot, Update(update_id=2, message=unauth_private_msg))

    # Assert neither debouncer, context, nor member_repo were touched
    assert mock_member_repo.upsert_member.call_count == 0
    assert mock_context_builder.add_message.call_count == 0
    assert mock_debouncer.on_message.call_count == 0

    # 3. Message from authorized group (-100111222) -> processed
    auth_group_msg = Message(
        message_id=3,
        date=now,
        chat=Chat(id=-100111222, type="supergroup", title="Main Group"),
        from_user=User(id=2, is_bot=False, first_name="Alice"),
        text="Hello authorized group",
    )
    await dp.feed_update(bot, Update(update_id=3, message=auth_group_msg))
    assert mock_member_repo.upsert_member.call_count == 1
    assert mock_context_builder.add_message.call_count == 1
    assert mock_debouncer.on_message.call_count == 1

    # 4. Message from authorized admin (111) in private chat -> processed (no debouncer call!)
    sent_bot_reply = Message(
        message_id=5,
        date=now,
        chat=Chat(id=111, type="private"),
        from_user=User(id=999, is_bot=True, first_name="Bot"),
        text="Reply",
    )
    auth_admin_msg = Message(
        message_id=4,
        date=now,
        chat=Chat(id=111, type="private"),
        from_user=User(id=111, is_bot=False, first_name="Admin"),
        text="Hello bot",
    )
    with patch.object(Message, "reply", new_callable=AsyncMock) as mock_reply:
        mock_reply.return_value = sent_bot_reply
        await dp.feed_update(bot, Update(update_id=4, message=auth_admin_msg))

    assert mock_debouncer.on_message.call_count == 1  # debouncer NOT called for admin private
    assert mock_context_builder.add_message.call_count == 3  # +admin msg +bot reply


@pytest.mark.asyncio
async def test_handle_group_message_reply_returning_none():
    """Verify handle_group_message handles None return from message.reply gracefully."""
    user = User(id=123, is_bot=False, first_name="Alice")
    chat = Chat(id=-100111222, type="supergroup", title="Test Group")

    bot_mock = MagicMock()
    bot_mock.id = 999

    message = MagicMock(spec=Message)
    message.message_id = 50
    message.from_user = user
    message.chat = chat
    message.text = "Bot, help me!"
    message.caption = None
    message.date = datetime.now(UTC)
    message.reply_to_message = None
    message.entities = None
    message.caption_entities = None
    message.bot = bot_mock
    message.reply = AsyncMock(return_value=None)

    member_repo = MagicMock(upsert_member=AsyncMock())
    context_builder = MagicMock(add_message=AsyncMock(), get_context=AsyncMock(return_value=[]))
    debouncer = MagicMock(on_message=AsyncMock())
    mention_detector = MagicMock(is_addressed=MagicMock(return_value=True))
    response_service = MagicMock(generate_response=AsyncMock(return_value="Help is on the way!"))

    await handle_group_message(
        message=message,
        member_repo=member_repo,
        context_builder=context_builder,
        debouncer=debouncer,
        mention_detector=mention_detector,
        response_service=response_service,
    )

    # Verify message.reply was called and bot response saved without crash
    message.reply.assert_awaited_once_with("Help is on the way!")
    assert context_builder.add_message.call_count == 2
    bot_saved_msg: ChatMessage = context_builder.add_message.call_args_list[1][1]["msg"]
    assert bot_saved_msg.text == "Help is on the way!"
    assert bot_saved_msg.user_id == 999
    assert bot_saved_msg.display_name == "Bot"
