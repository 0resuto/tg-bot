"""Protocol for the long-term memory backend abstraction.

Services call this protocol instead of Graphiti directly, so the graph
backend can be mocked in tests or swapped later without touching business
logic.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from bot.domain.models import MemoryFact, MemoryStats


class MemoryBackend(Protocol):
    """Abstract long-term memory store (knowledge graph)."""

    async def ingest_episode(
        self,
        text: str,
        group_id: str,
        source_user_name: str,
        reference_time: datetime,
    ) -> None:
        """Ingest a message or message batch into the knowledge graph.

        Args:
            text: The episode body (may contain multiple messages).
            group_id: Chat-scoping namespace (typically ``str(chat_id)``).
            source_user_name: Display name of the primary speaker.
            reference_time: Wall-clock time of the episode.
        """
        ...

    async def search_quick(
        self,
        user_name: str,
        group_id: str,
        *,
        limit: int = 5,
    ) -> list[MemoryFact]:
        """Level 1 — lightweight profile lookup for a specific user.

        Returns the most salient facts about *user_name* within the given
        chat namespace.  This should be cheap (mostly graph traversal, no
        heavy LLM reasoning).
        """
        ...

    async def search_deep(
        self,
        query: str,
        group_id: str,
        *,
        limit: int = 15,
    ) -> list[MemoryFact]:
        """Level 2 — full semantic search across the knowledge graph.

        Performs hybrid retrieval (vector + BM25 + graph traversal) scoped
        to *group_id*.  More expensive than :meth:`search_quick`.
        """
        ...

    async def delete_facts(
        self,
        description: str,
        group_id: str,
    ) -> int:
        """Delete facts matching a natural-language description.

        Returns:
            The number of facts deleted.
        """
        ...

    async def get_stats(
        self,
        group_id: str,
    ) -> MemoryStats:
        """Return memory statistics for the given chat namespace."""
        ...
