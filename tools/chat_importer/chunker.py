"""Conversation chunker for grouping chat messages into dialogue episodes.

Groups chronological messages by idle time threshold and maximum message count
into structured DialogueEpisode units for knowledge graph ingestion.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from bot.log import get_logger
from bot.models import ChatMessage
from tools.chat_importer.contracts import DialogueEpisodeContract

logger = get_logger(__name__)

# Runtime-validated dialogue episode contract
DialogueEpisode = DialogueEpisodeContract


def _normalize_dt(dt: datetime) -> datetime:
    """Normalize datetime to timezone-aware UTC for safe comparisons."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _format_speaker_line(msg: ChatMessage) -> str:
    """Format single message with speaker prefix."""
    speaker = (msg.display_name or "").strip()
    if not speaker:
        speaker = f"User {msg.user_id}" if msg.user_id else "Anonymous"
    return f"{speaker}: {msg.text.strip()}"


class ConversationChunker:
    """Groups messages into chronological dialogue episodes by idle gap and size."""

    def __init__(self, gap_minutes: int = 20, max_messages: int = 15) -> None:
        if gap_minutes <= 0:
            raise ValueError(f"gap_minutes must be positive, got {gap_minutes}")
        if max_messages <= 0:
            raise ValueError(f"max_messages must be positive, got {max_messages}")

        self.gap_minutes = gap_minutes
        self.max_messages = max_messages
        self.gap_seconds = gap_minutes * 60

    def _create_episode(self, chunk_messages: list[ChatMessage], index: int) -> DialogueEpisode:
        """Create DialogueEpisode from accumulated chunk messages."""
        chat_id = chunk_messages[0].chat_id
        formatted_lines = [_format_speaker_line(m) for m in chunk_messages]
        episode_text = "\n".join(formatted_lines)

        first_speaker = (chunk_messages[0].display_name or "").strip()
        if not first_speaker:
            first_speaker = (
                f"User {chunk_messages[0].user_id}" if chunk_messages[0].user_id else "Anonymous"
            )

        reference_time = chunk_messages[-1].timestamp

        return DialogueEpisode(
            episode_index=index,
            chat_id=chat_id,
            messages=chunk_messages,
            text=episode_text,
            source_user_name=first_speaker,
            reference_time=reference_time,
        )

    def chunk(self, messages: Sequence[ChatMessage]) -> list[DialogueEpisode]:
        """Group chronological messages into dialogue episodes."""
        if not messages:
            return []

        # Ensure strict chronological sorting
        sorted_messages = sorted(
            messages,
            key=lambda m: (_normalize_dt(m.timestamp), m.message_id),
        )

        episodes: list[DialogueEpisode] = []
        current_chunk: list[ChatMessage] = []
        current_index = 0

        for msg in sorted_messages:
            if not current_chunk:
                current_chunk.append(msg)
                continue

            prev_msg = current_chunk[-1]
            t_curr = _normalize_dt(msg.timestamp)
            t_prev = _normalize_dt(prev_msg.timestamp)
            delta_seconds = abs((t_curr - t_prev).total_seconds())

            reached_max = len(current_chunk) >= self.max_messages
            exceeded_gap = delta_seconds > self.gap_seconds

            if reached_max or exceeded_gap:
                episodes.append(self._create_episode(current_chunk, current_index))
                current_index += 1
                current_chunk = [msg]
            else:
                current_chunk.append(msg)

        if current_chunk:
            episodes.append(self._create_episode(current_chunk, current_index))

        logger.debug(
            "Conversation chunking complete",
            total_messages=len(sorted_messages),
            total_episodes=len(episodes),
            gap_minutes=self.gap_minutes,
            max_messages=self.max_messages,
        )

        return episodes
