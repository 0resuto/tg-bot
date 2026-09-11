from __future__ import annotations

import json
from datetime import datetime

import redis.asyncio as redis

from bot.domain.models import ChatMessage, MemoryFact, MemoryStats
from bot.interfaces.memory import MemoryBackend
from bot.log import get_logger
from bot.repositories.token_usage_repo import TokenUsageRepository
from bot.services.sensitive_filter import SensitiveFilter

logger = get_logger(__name__)


class MemoryService:
    """Orchestrates memory ingestion and retrieval."""

    def __init__(
        self,
        memory: MemoryBackend,
        sensitive_filter: SensitiveFilter,
        token_repo: TokenUsageRepository,
        redis_client: redis.Redis | None = None,
        redis: redis.Redis | None = None,
        cache_ttl: int = 300,
        search_limit_quick: int = 5,
        search_limit_deep: int = 15,
    ) -> None:
        self.memory = memory
        self.sensitive_filter = sensitive_filter
        self.token_repo = token_repo
        client = redis_client or redis
        if client is None:
            raise ValueError("Either redis_client or redis must be provided")
        self.redis = client
        self.cache_ttl = cache_ttl
        self.search_limit_quick = search_limit_quick
        self.search_limit_deep = search_limit_deep

    async def ingest_messages(
        self, chat_id: int, user_id: int, messages: list[ChatMessage]
    ) -> None:
        """Formats messages into an episode and ingests into memory."""
        if not messages:
            return

        # Format messages as episode text
        lines = [f"{msg.display_name}: {msg.text}" for msg in messages]
        episode_text = "\n".join(lines)

        # Run through sensitive filter
        filtered_text, categories = self.sensitive_filter.filter_for_ingestion(episode_text)

        if filtered_text is None:
            logger.info(
                "Skipping memory ingestion due to sensitive filter",
                chat_id=chat_id,
                user_id=user_id,
            )
            return

        source_user_name = messages[0].display_name
        reference_time = messages[-1].timestamp

        try:
            # Memory backend ingestion
            # Note: The underlying memory implementation should be async or wrapped in an executor
            # Assuming it exposes an async interface here or handles it internally
            await self.memory.ingest_episode(
                text=filtered_text,
                group_id=str(chat_id),
                source_user_name=source_user_name,
                reference_time=reference_time,
            )
        except Exception as e:
            logger.error("Error during memory ingestion", exc_info=e, chat_id=chat_id)

    async def get_quick_facts(self, user_name: str, chat_id: int) -> list[MemoryFact]:
        """Retrieve Level 1 quick facts with caching."""
        cache_key = f"memory:quick:{chat_id}:{user_name}"
        cached_data = await self.redis.get(cache_key)

        if cached_data:
            try:
                facts_data = json.loads(cached_data)
                return [
                    MemoryFact(
                        fact_text=f["fact_text"],
                        subject_name=f.get("subject_name"),
                        confidence=f.get("confidence", 1.0),
                        created_at=datetime.fromisoformat(f["created_at"])
                        if f.get("created_at")
                        else None,
                    )
                    for f in facts_data
                ]
            except Exception as e:
                logger.warning("Error parsing cached facts", exc_info=e, cache_key=cache_key)

        # Cache miss, retrieve from memory backend
        try:
            facts = await self.memory.search_quick(
                user_name=user_name, group_id=str(chat_id), limit=self.search_limit_quick
            )

            # Serialize for cache
            facts_list = []
            for f in facts:
                facts_list.append(
                    {
                        "fact_text": f.fact_text,
                        "subject_name": f.subject_name,
                        "confidence": f.confidence,
                        "created_at": f.created_at.isoformat() if f.created_at else None,
                    }
                )

            await self.redis.set(cache_key, json.dumps(facts_list), ex=self.cache_ttl)
            return facts
        except Exception as e:
            logger.error(
                "Error retrieving quick facts", exc_info=e, user_name=user_name, chat_id=chat_id
            )
            return []

    async def search_memories(self, query: str, chat_id: int) -> list[MemoryFact]:
        """Retrieve Level 2 deep search facts based on context query."""
        try:
            return await self.memory.search_deep(
                query=query, group_id=str(chat_id), limit=self.search_limit_deep
            )
        except Exception as e:
            logger.error("Error during deep memory search", exc_info=e, chat_id=chat_id)
            return []

    async def forget_fact(self, description: str, chat_id: int) -> int:
        """Deletes facts matching the description."""
        try:
            return await self.memory.delete_facts(description=description, group_id=str(chat_id))
        except Exception as e:
            logger.error("Error deleting facts", exc_info=e, chat_id=chat_id)
            return 0

    async def get_stats(self, chat_id: int) -> MemoryStats:
        """Get stats for a specific chat group."""
        try:
            return await self.memory.get_stats(group_id=str(chat_id))
        except Exception as e:
            logger.error("Error getting memory stats", exc_info=e, chat_id=chat_id)
            return MemoryStats()
