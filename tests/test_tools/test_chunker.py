"""Unit tests for ConversationChunker and DialogueEpisode."""

from datetime import UTC, datetime, timedelta

import pytest

from bot.models import ChatMessage
from tools.chat_importer.chunker import ConversationChunker


def test_chunker_empty_messages() -> None:
    """Empty message sequence should return empty episode list."""
    chunker = ConversationChunker()
    assert chunker.chunk([]) == []


def test_chunker_invalid_args() -> None:
    """Non-positive arguments should raise ValueError."""
    with pytest.raises(ValueError, match="gap_minutes must be positive"):
        ConversationChunker(gap_minutes=0)
    with pytest.raises(ValueError, match="gap_minutes must be positive"):
        ConversationChunker(gap_minutes=-5)
    with pytest.raises(ValueError, match="max_messages must be positive"):
        ConversationChunker(max_messages=0)
    with pytest.raises(ValueError, match="max_messages must be positive"):
        ConversationChunker(max_messages=-10)


def test_chunker_single_message() -> None:
    """Single message should produce single episode with matching metadata."""
    t0 = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
    msg = ChatMessage(
        chat_id=-100123,
        user_id=1,
        text="Hello world",
        timestamp=t0,
        message_id=10,
        display_name="Alice",
    )

    chunker = ConversationChunker(gap_minutes=20, max_messages=15)
    episodes = chunker.chunk([msg])

    assert len(episodes) == 1
    ep = episodes[0]
    assert ep.episode_index == 0
    assert ep.chat_id == -100123
    assert ep.source_user_name == "Alice"
    assert ep.reference_time == t0
    assert ep.text == "Alice: Hello world"
    assert ep.formatted_text == ep.text
    assert len(ep.messages) == 1


def test_chunker_max_messages_limit() -> None:
    """Messages exceeding max_messages should be partitioned into multiple episodes."""
    t0 = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
    messages = [
        ChatMessage(
            chat_id=-100123,
            user_id=i,
            text=f"Message {i}",
            timestamp=t0 + timedelta(seconds=i),
            message_id=100 + i,
            display_name=f"User_{i}",
        )
        for i in range(25)
    ]

    chunker = ConversationChunker(gap_minutes=20, max_messages=10)
    episodes = chunker.chunk(messages)

    assert len(episodes) == 3
    assert len(episodes[0].messages) == 10
    assert len(episodes[1].messages) == 10
    assert len(episodes[2].messages) == 5
    assert episodes[0].episode_index == 0
    assert episodes[1].episode_index == 1
    assert episodes[2].episode_index == 2


def test_chunker_idle_gap() -> None:
    """Conversations with idle gap exceeding threshold should split into new episodes."""
    t0 = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
    msg1 = ChatMessage(-1001, 1, "Start conversation", t0, 1, "Alice")
    msg2 = ChatMessage(-1001, 2, "Reply in 5 minutes", t0 + timedelta(minutes=5), 2, "Bob")
    # 25 minutes gap (exceeds 20 minutes default)
    msg3 = ChatMessage(-1001, 1, "New topic after 25 mins", t0 + timedelta(minutes=30), 3, "Alice")

    chunker = ConversationChunker(gap_minutes=20, max_messages=15)
    episodes = chunker.chunk([msg1, msg2, msg3])

    assert len(episodes) == 2
    assert len(episodes[0].messages) == 2
    assert episodes[0].messages[0].text == "Start conversation"
    assert episodes[0].messages[1].text == "Reply in 5 minutes"

    assert len(episodes[1].messages) == 1
    assert episodes[1].messages[0].text == "New topic after 25 mins"


def test_chunker_chronological_reordering() -> None:
    """Messages out of chronological order should be sorted before chunking."""
    t0 = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
    msg_late = ChatMessage(-1001, 1, "Later message", t0 + timedelta(minutes=5), 2, "Alice")
    msg_early = ChatMessage(-1001, 2, "Earlier message", t0, 1, "Bob")

    chunker = ConversationChunker(gap_minutes=20, max_messages=15)
    episodes = chunker.chunk([msg_late, msg_early])

    assert len(episodes) == 1
    assert episodes[0].messages[0].text == "Earlier message"
    assert episodes[0].messages[1].text == "Later message"
    assert episodes[0].source_user_name == "Bob"


def test_chunker_speaker_formatting_fallbacks() -> None:
    """Display name fallback to User <id> or Anonymous when display_name is empty."""
    t0 = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
    msg1 = ChatMessage(-1001, 555, "Hello", t0, 1, "")
    msg2 = ChatMessage(-1001, 0, "Guest note", t0 + timedelta(seconds=10), 2, "")

    chunker = ConversationChunker(gap_minutes=20, max_messages=15)
    episodes = chunker.chunk([msg1, msg2])

    assert len(episodes) == 1
    lines = episodes[0].text.split("\n")
    assert lines[0] == "User 555: Hello"
    assert lines[1] == "Anonymous: Guest note"


def test_chunker_mixed_timezone_awareness() -> None:
    """Mixing naive and timezone-aware datetimes should not cause TypeError."""
    t_naive = datetime(2024, 1, 1, 12, 0, 0)
    t_aware = datetime(2024, 1, 1, 12, 5, 0, tzinfo=UTC)

    msg1 = ChatMessage(-1001, 1, "Naive dt", t_naive, 1, "Alice")
    msg2 = ChatMessage(-1001, 2, "Aware dt", t_aware, 2, "Bob")

    chunker = ConversationChunker(gap_minutes=20, max_messages=15)
    episodes = chunker.chunk([msg1, msg2])

    assert len(episodes) == 1
    assert len(episodes[0].messages) == 2


def test_chunker_exact_idle_gap_boundary() -> None:
    """Idle gap exactly equal to threshold must NOT split; 1 second over MUST split."""
    from dataclasses import FrozenInstanceError

    t0 = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
    msg1 = ChatMessage(-1001, 1, "Start", t0, 1, "Alice")

    # Exactly 20 minutes (1200 seconds): delta == gap, should NOT split
    msg_exact = ChatMessage(-1001, 2, "Exact 20m", t0 + timedelta(minutes=20), 2, "Bob")
    chunker = ConversationChunker(gap_minutes=20, max_messages=15)
    episodes_exact = chunker.chunk([msg1, msg_exact])
    assert len(episodes_exact) == 1
    assert episodes_exact[0].reference_time == msg_exact.timestamp
    assert episodes_exact[0].reference_time != msg1.timestamp

    # Immutability check
    from pydantic import ValidationError

    with pytest.raises((FrozenInstanceError, ValidationError)):
        episodes_exact[0].text = "mutated"  # type: ignore[misc]

    # Exactly 20 minutes + 1 second: delta > gap, MUST split
    msg_over = ChatMessage(-1001, 2, "Over 20m", t0 + timedelta(minutes=20, seconds=1), 3, "Bob")
    episodes_over = chunker.chunk([msg1, msg_over])
    assert len(episodes_over) == 2
