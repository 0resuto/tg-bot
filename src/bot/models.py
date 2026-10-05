"""Domain models, enumerations, and protocols.

These are framework-agnostic representations and interfaces that serve as
the common language across application layers.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


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
    valid_at: datetime | None = None
    reference_time: datetime | None = None


@dataclass(frozen=True, slots=True)
class MemoryStats:
    """Aggregated statistics for a chat's knowledge graph partition."""

    total_entities: int = 0
    total_relations: int = 0
    total_episodes: int = 0
    last_ingestion_at: datetime | None = None


class EmptyLLMResponseError(RuntimeError):
    """Raised when an LLM provider yields no usable content."""


class MemoryUnavailableError(RuntimeError):
    """Raised when the knowledge graph (memory backend) cannot be reached."""


class LLMProvider(Protocol):
    """Abstract LLM chat-completion provider."""

    async def generate_response(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        max_tokens: int = 1024,
    ) -> str:
        """Generate a chat completion.

        Implementations must return a non-empty string or raise
        :class:`EmptyLLMResponseError` when the model produced no content.
        """
        ...

    async def close(self) -> None:
        """Close provider resources and underlying connection pools."""
        ...


class MemoryBackend(Protocol):
    """Abstract long-term memory store (knowledge graph)."""

    async def close(self) -> None:
        """Close storage resources and underlying connection pools."""
        ...

    async def ingest_episode(
        self,
        text: str,
        group_id: str,
        source_user_name: str,
        reference_time: datetime,
    ) -> None:
        """Ingest a message or message batch into the knowledge graph."""
        ...

    async def search_quick(
        self,
        user_name: str,
        group_id: str,
        *,
        limit: int = 5,
    ) -> list[MemoryFact]:
        """Level 1 — lightweight profile lookup for a specific user."""
        ...

    async def search_deep(
        self,
        query: str,
        group_id: str,
        *,
        limit: int = 15,
        valid_at_range: tuple[datetime, datetime] | None = None,
    ) -> list[MemoryFact]:
        """Level 2 — full semantic search, optionally limited to a time window."""
        ...

    async def get_stats(
        self,
        group_id: str,
    ) -> MemoryStats:
        """Return memory statistics for the given chat namespace."""
        ...
