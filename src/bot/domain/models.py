"""Framework-agnostic domain models.

These are plain dataclasses with no dependency on SQLAlchemy, aiogram, or any
other framework.  They serve as the lingua franca between layers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from bot.domain.enums import OperationType


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class MemberIdentity:
    """Snapshot of a Telegram user's identity at the time of a message."""

    telegram_user_id: int
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None

    @property
    def display_name(self) -> str:
        """Best-effort human-readable name."""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        if self.first_name:
            return self.first_name
        if self.username:
            return self.username
        return str(self.telegram_user_id)


@dataclass(frozen=True, slots=True)
class ChatMessage:
    """A single text message in a group chat."""

    chat_id: int
    user_id: int
    text: str
    timestamp: datetime
    message_id: int
    display_name: str = ""
    reply_to_message_id: int | None = None


@dataclass(frozen=True, slots=True)
class MemoryFact:
    """A single fact extracted from the knowledge graph."""

    fact_text: str
    subject_name: str | None = None
    confidence: float = 1.0
    created_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class UserSummary:
    """Cached summary of what the bot knows about a chat member."""

    user_id: int
    display_name: str
    summary_text: str
    fact_count: int = 0
    last_updated: datetime | None = None


@dataclass(frozen=True, slots=True)
class TokenUsageRecord:
    """Token consumption for a single LLM call."""

    chat_id: int
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    operation: OperationType
    telegram_user_id: int | None = None
    timestamp: datetime = field(default_factory=_utcnow)
