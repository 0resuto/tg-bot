"""Service for querying and managing memory facts and token metrics."""

from __future__ import annotations

import asyncio
from typing import Any

from neo4j import GraphDatabase

from bot.config import Settings
from bot.log import get_logger
from bot.services.memory_service import MemoryService
from bot.web.services.graph_service import _serialize_neo4j_val

logger = get_logger(__name__)


class MemoryQueryService:
    """Provides memory queries, stats aggregation, and forget operations."""

    def __init__(
        self,
        settings: Settings,
        memory_service: MemoryService | None,
    ) -> None:
        self.settings = settings
        self.memory_service = memory_service

    def _fetch_raw_facts(self, chat_id: int | None = None) -> list[dict[str, Any]]:
        """Query Neo4j directly for extracted facts."""
        if not self.settings.neo4j_password:
            return []

        driver = GraphDatabase.driver(
            self.settings.neo4j_uri,
            auth=(self.settings.neo4j_user, self.settings.neo4j_password),
        )
        extracted: list[dict[str, Any]] = []
        try:
            with driver.session() as session:
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

                res = session.run(query, params)
                for rec in res:
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
            driver.close()

        return extracted

    async def get_memories(self, chat_id: int | None = None) -> list[dict[str, Any]]:
        """Retrieve recent facts list."""
        facts = await asyncio.to_thread(self._fetch_raw_facts, chat_id)
        if not facts and self.memory_service and chat_id is not None:
            stats = await self.memory_service.get_stats(chat_id)
            facts = [
                {
                    "subject": "Graphiti Memory",
                    "fact_text": f"Active graph stats: {stats}",
                    "created_at": None,
                }
            ]
        return facts

    async def forget_fact(self, description: str, chat_id: int) -> int:
        """Remove facts matching description from the knowledge graph."""
        if not self.memory_service:
            return 0
        return await self.memory_service.forget_fact(description, chat_id)

    async def get_stats(self, chat_id: int | None = None) -> dict[str, Any]:
        """Aggregate memory and token usage metrics."""
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
