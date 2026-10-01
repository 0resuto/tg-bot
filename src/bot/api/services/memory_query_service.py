"""Service for querying and managing memory facts and graph statistics."""

from __future__ import annotations

from typing import Any

from neo4j import AsyncDriver, AsyncGraphDatabase

from bot.api.services.graph_service import _serialize_neo4j_val
from bot.config import Settings
from bot.log import get_logger
from bot.services.memory_service import MemoryService

logger = get_logger(__name__)


class MemoryQueryService:
    """Provides memory queries and stats aggregation."""

    def __init__(
        self,
        settings: Settings,
        memory_service: MemoryService | None,
        driver: AsyncDriver | None = None,
    ) -> None:
        self.settings = settings
        self.memory_service = memory_service
        self.driver = driver

    async def _fetch_raw_facts(self, chat_id: int | None = None) -> list[dict[str, Any]]:
        """Query Neo4j directly for extracted facts."""
        if not self.settings.neo4j_password:
            return []

        driver = self.driver
        created_driver = False
        if driver is None:
            driver = AsyncGraphDatabase.driver(
                self.settings.neo4j_uri,
                auth=(self.settings.neo4j_user, self.settings.neo4j_password),
            )
            created_driver = True
        extracted: list[dict[str, Any]] = []
        try:
            async with driver.session() as session:
                query = """
                    MATCH (n)-[r]->(m)
                    WHERE r.fact IS NOT NULL
                    RETURN coalesce(n.name, 'Fact') as subject, r.fact as fact, r.created_at as created_at
                    ORDER BY r.created_at DESC
                    LIMIT 100
                """
                params: dict[str, Any] = {}
                if chat_id is not None:
                    query = """
                        MATCH (n)-[r]->(m)
                        WHERE r.fact IS NOT NULL AND r.group_id = $group_id
                        RETURN coalesce(n.name, 'Fact') as subject, r.fact as fact, r.created_at as created_at
                        ORDER BY r.created_at DESC
                        LIMIT 100
                    """
                    params["group_id"] = str(chat_id)

                res = await session.run(query, params)
                async for rec in res:
                    extracted.append(
                        {
                            "subject": rec.get("subject") or "Fact",
                            "fact_text": rec.get("fact") or "",
                            "created_at": _serialize_neo4j_val(rec.get("created_at")),
                        }
                    )
        except Exception as exc:
            logger.warning("Failed to fetch raw facts from Neo4j", error=str(exc))
        finally:
            if created_driver:
                await driver.close()

        return extracted

    async def get_memories(self, chat_id: int | None = None) -> list[dict[str, Any]]:
        """Retrieve recent facts list."""
        return await self._fetch_raw_facts(chat_id)

    async def get_stats(self, chat_id: int | None = None) -> dict[str, Any]:
        """Aggregate memory metrics."""
        mem_stats: dict[str, Any] = {"status": "offline"}
        if self.memory_service and chat_id is not None:
            try:
                stats = await self.memory_service.get_stats(chat_id)
                mem_stats = {
                    "total_entities": stats.total_entities,
                    "total_relations": stats.total_relations,
                    "total_episodes": stats.total_episodes,
                    "last_ingestion_at": (
                        stats.last_ingestion_at.isoformat() if stats.last_ingestion_at else None
                    ),
                }
            except Exception as exc:
                mem_stats = {"status": "error", "error": str(exc)}

        return {
            "memory_stats": mem_stats,
        }
