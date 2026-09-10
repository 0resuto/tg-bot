from __future__ import annotations

from datetime import UTC, datetime, timedelta

from bot.domain.models import ChatMessage
from bot.services.context_builder import ContextBuilder


async def test_context_builder(fake_redis):
    builder = ContextBuilder(redis_client=fake_redis, window_minutes=15, min_messages=2)

    now = datetime.now(UTC)

    # Add old message (30 mins ago)
    old_msg = ChatMessage(
        chat_id=100,
        user_id=1,
        text="Old message",
        timestamp=now - timedelta(minutes=30),
        message_id=10,
        display_name="Alice",
    )
    await builder.add_message(old_msg)

    # Add recent message (5 mins ago)
    recent_msg = ChatMessage(
        chat_id=100,
        user_id=2,
        text="Recent message",
        timestamp=now - timedelta(minutes=5),
        message_id=11,
        display_name="Bob",
    )
    await builder.add_message(recent_msg)

    # Should return both because min_messages=2 even though old_msg is >15 mins
    context = await builder.get_context(chat_id=100)
    assert len(context) == 2
    assert context[0].text == "Old message"
    assert context[1].text == "Recent message"

    # Add a third message (recent)
    recent_msg_2 = ChatMessage(
        chat_id=100,
        user_id=1,
        text="Another recent message",
        timestamp=now - timedelta(minutes=2),
        message_id=12,
        display_name="Alice",
    )
    await builder.add_message(recent_msg_2)

    # Now we have 2 recent messages within 15 min window, so old_msg should be excluded
    context_filtered = await builder.get_context(chat_id=100)
    assert len(context_filtered) == 2
    assert context_filtered[0].text == "Recent message"
    assert context_filtered[1].text == "Another recent message"
