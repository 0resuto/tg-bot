from __future__ import annotations

from datetime import datetime

from bot.log import get_logger
from bot.models import ChatMessage, MemoryBackend, MemoryFact, MemoryStats
from bot.services.message_filter import MessageNoiseFilter, default_noise_filter

logger = get_logger(__name__)


class MemoryService:
    """Orchestrates memory ingestion and retrieval."""

    def __init__(
        self,
        memory: MemoryBackend,
        search_limit_quick: int = 5,
        search_limit_deep: int = 15,
        noise_filter: MessageNoiseFilter | None = None,
    ) -> None:
        self.memory = memory
        self.search_limit_quick = search_limit_quick
        self.search_limit_deep = search_limit_deep
        self.noise_filter = noise_filter or default_noise_filter

    async def ingest_messages(
        self, chat_id: int, user_id: int, messages: list[ChatMessage]
    ) -> None:
        """Formats messages into an episode and ingests into memory."""
        if not messages:
            return

        meaningful_messages = self.noise_filter.filter_batch(messages)
        if not meaningful_messages:
            logger.debug(
                "Skipping memory ingestion: all messages filtered as conversational noise",
                chat_id=chat_id,
                user_id=user_id,
                total_dropped=len(messages),
            )
            return

        episode_text = "\n".join(f"{msg.display_name}: {msg.text}" for msg in meaningful_messages)
        source_user_name = meaningful_messages[0].display_name
        reference_time = meaningful_messages[-1].timestamp

        try:
            await self.memory.ingest_episode(
                text=episode_text,
                group_id=str(chat_id),
                source_user_name=source_user_name,
                reference_time=reference_time,
            )
        except Exception as e:
            logger.error("Error during memory ingestion", exc_info=e, chat_id=chat_id)

    async def get_quick_facts(self, user_name: str, chat_id: int) -> list[MemoryFact]:
        """Retrieve Level 1 quick facts directly from memory backend."""
        try:
            return await self.memory.search_quick(
                user_name=user_name, group_id=str(chat_id), limit=self.search_limit_quick
            )
        except Exception as e:
            logger.error(
                "Error retrieving quick facts",
                exc_info=e,
                user_name=user_name,
                chat_id=chat_id,
            )
            return []

    async def search_memories(
        self,
        query: str,
        chat_id: int,
        valid_at_range: tuple[datetime, datetime] | None = None,
    ) -> list[MemoryFact]:
        """Retrieve Level 2 deep memories, optionally limited to a time window."""
        try:
            return await self.memory.search_deep(
                query=query,
                group_id=str(chat_id),
                limit=self.search_limit_deep,
                valid_at_range=valid_at_range,
            )
        except Exception as e:
            logger.error("Error retrieving deep memories", exc_info=e, query=query, chat_id=chat_id)
            return []

    async def get_stats(self, chat_id: int) -> MemoryStats:
        """Retrieve graph memory statistics."""
        try:
            return await self.memory.get_stats(group_id=str(chat_id))
        except Exception as e:
            logger.error("Error retrieving memory stats", exc_info=e, chat_id=chat_id)
            return MemoryStats()
