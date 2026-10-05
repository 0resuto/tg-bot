"""Graphiti memory backend implementation."""

from __future__ import annotations

import inspect
import uuid
from datetime import UTC, datetime
from typing import Any

from graphiti_core import Graphiti
from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig
from graphiti_core.llm_client.config import LLMConfig
from graphiti_core.llm_client.openai_client import OpenAIClient
from graphiti_core.nodes import EpisodeType
from graphiti_core.search.search_filters import ComparisonOperator, DateFilter, SearchFilters
from neo4j.exceptions import ServiceUnavailable, SessionExpired, TransientError
from pydantic import BaseModel, Field
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from bot.log import get_logger
from bot.models import MemoryBackend, MemoryFact, MemoryStats

logger = get_logger(__name__)

# How many extra candidates to fetch when a time window is applied, so that
# post-filtering by fact time still has a chance to fill the requested limit.
_WINDOW_FETCH_MULTIPLIER = 4

NEO4J_TRANSIENT_EXCEPTIONS = (
    ServiceUnavailable,
    SessionExpired,
    TransientError,
    ConnectionError,
    TimeoutError,
)

retry_neo4j = retry(
    wait=wait_exponential(multiplier=1, min=2, max=10),
    stop=stop_after_attempt(3),
    retry=retry_if_exception_type(NEO4J_TRANSIENT_EXCEPTIONS),
    reraise=True,
)


class Person(BaseModel):
    """A human participant, user, individual, or named person mentioned in the conversation."""

    role: str | None = Field(default=None, description="Role or relationship of the person")


class Animal(BaseModel):
    """An animal, pet, domestic creature, or beast (e.g. dog, cat, parrot, horse)."""

    species: str | None = Field(default=None, description="Species or breed of animal")


class Item(BaseModel):
    """A physical object, tool, vehicle, gadget, equipment, clothing, or manufactured item (e.g. bicycle, car, phone, coffee machine)."""

    category: str | None = Field(default=None, description="Category of the item")


class Location(BaseModel):
    """A geographical location, city, country, venue, building, restaurant, or place (e.g. Rome, office, park, Tokyo)."""


class Concept(BaseModel):
    """An abstract concept, hobby, skill, sport, project, topic, event, or phenomenon (e.g. cycling, vacation, programming, concert, weather)."""


DEFAULT_ENTITY_TYPES: dict[str, type[BaseModel]] = {
    "Person": Person,
    "Animal": Animal,
    "Item": Item,
    "Location": Location,
    "Concept": Concept,
}


class GraphitiMemoryBackend(MemoryBackend):
    """Memory backend implementation using Graphiti and Neo4j."""

    def __init__(
        self,
        neo4j_uri: str,
        neo4j_user: str,
        neo4j_password: str,
        openai_api_key: str,
        extraction_model: str,
        embedding_model: str,
        entity_types: dict[str, type[BaseModel]] | None = None,
    ):
        self.entity_types = entity_types if entity_types is not None else DEFAULT_ENTITY_TYPES

        llm_client = OpenAIClient(LLMConfig(api_key=openai_api_key, model=extraction_model))
        embedder = OpenAIEmbedder(
            OpenAIEmbedderConfig(api_key=openai_api_key, embedding_model=embedding_model)
        )

        self.client = Graphiti(
            uri=neo4j_uri,
            user=neo4j_user,
            password=neo4j_password,
            llm_client=llm_client,
            embedder=embedder,
        )

    async def close(self) -> None:
        """Close connections and release Neo4j driver connection pool."""
        close = getattr(self.client, "close", None)
        if close is not None:
            res = close()
            if inspect.isawaitable(res):
                await res
        driver = getattr(self.client, "driver", None)
        if driver and hasattr(driver, "close"):
            res = driver.close()
            if inspect.isawaitable(res):
                await res

    @retry_neo4j
    async def ingest_episode(
        self, text: str, group_id: str, source_user_name: str, reference_time: datetime
    ) -> None:
        """Ingest a message episode into Graphiti."""
        episode_name = f"episode_{uuid.uuid4().hex[:8]}"
        await self.client.add_episode(
            name=episode_name,
            episode_body=text,
            source_description=f"Message from {source_user_name}",
            source=EpisodeType.message,
            group_id=group_id,
            reference_time=reference_time,
            entity_types=self.entity_types,
        )
        logger.debug("ingested_episode", episode=episode_name, group_id=group_id)

    @retry_neo4j
    async def search_quick(
        self, user_name: str, group_id: str, *, limit: int = 5
    ) -> list[MemoryFact]:
        """Perform a quick search for user facts."""
        return await self.search_deep(f"Key facts about {user_name}", group_id, limit=limit)

    @retry_neo4j
    async def search_deep(
        self,
        query: str,
        group_id: str,
        *,
        limit: int = 10,
        valid_at_range: tuple[datetime, datetime] | None = None,
    ) -> list[MemoryFact]:
        """Perform a deep semantic search, optionally limited to a time window.

        When a window is requested, dated facts are filtered server-side by
        Graphiti (``EntityEdge.valid_at``) so in-window facts are not lost to
        relevance ranking. Facts with an unknown ``valid_at`` are recovered via
        a second query and matched by the episode ``reference_time`` (when the
        fact was mentioned).
        """
        if valid_at_range is None:
            results = await self.client.search(
                query=query,
                group_ids=[group_id],
                num_results=limit,
            )
            return self._map_results_to_facts(results)[:limit]

        start, end = valid_at_range
        results = await self.client.search(
            query=query,
            group_ids=[group_id],
            num_results=limit,
            search_filter=SearchFilters(
                valid_at=[
                    [
                        DateFilter(
                            date=start,
                            comparison_operator=ComparisonOperator.greater_than_equal,
                        ),
                        DateFilter(
                            date=end,
                            comparison_operator=ComparisonOperator.less_than,
                        ),
                    ]
                ]
            ),
        )
        facts = [f for f in self._map_results_to_facts(results) if self._in_window(f, start, end)]

        if len(facts) < limit:
            facts = await self._top_up_undated_facts(facts, query, group_id, start, end, limit)

        logger.debug(
            "search_deep_window",
            group_id=group_id,
            start=start.isoformat(),
            end=end.isoformat(),
            facts=len(facts),
        )
        return facts[:limit]

    async def _top_up_undated_facts(
        self,
        facts: list[MemoryFact],
        query: str,
        group_id: str,
        start: datetime,
        end: datetime,
        limit: int,
    ) -> list[MemoryFact]:
        """Merge in facts without ``valid_at`` whose mention time is in the window."""
        results = await self.client.search(
            query=query,
            group_ids=[group_id],
            num_results=limit * _WINDOW_FETCH_MULTIPLIER,
        )
        seen = {fact.fact_text for fact in facts}
        for fact in self._map_results_to_facts(results):
            if len(facts) >= limit:
                break
            if fact.valid_at is not None or fact.fact_text in seen:
                continue
            if self._in_window(fact, start, end):
                facts.append(fact)
                seen.add(fact.fact_text)
        return facts

    @staticmethod
    def _in_window(fact: MemoryFact, start: datetime, end: datetime) -> bool:
        """Return True if the fact's event time falls into [start, end)."""
        event_time = fact.valid_at or fact.reference_time
        if event_time is None:
            return False
        if event_time.tzinfo is None:
            event_time = event_time.replace(tzinfo=UTC)
        return start <= event_time < end

    @retry_neo4j
    async def get_stats(self, group_id: str) -> MemoryStats:
        """Get graph statistics for the given group."""
        entities_res = await self.client.driver.execute_query(
            "MATCH (n) WHERE n.group_id = $group_id RETURN count(n) as cnt",
            params={"group_id": group_id},
        )
        relations_res = await self.client.driver.execute_query(
            "MATCH ()-[r]->() WHERE r.group_id = $group_id RETURN count(r) as cnt",
            params={"group_id": group_id},
        )
        episodes_res = await self.client.driver.execute_query(
            "MATCH (e:Episodic) WHERE e.group_id = $group_id "
            "RETURN count(e) as cnt, max(e.created_at) as last_ingested",
            params={"group_id": group_id},
        )

        last_ingested = None
        if episodes_res.records and episodes_res.records[0]["last_ingested"]:
            raw_ts = episodes_res.records[0]["last_ingested"]
            if hasattr(raw_ts, "to_native"):
                last_ingested = raw_ts.to_native()
            elif isinstance(raw_ts, datetime):
                last_ingested = raw_ts
            elif isinstance(raw_ts, str):
                try:
                    last_ingested = datetime.fromisoformat(raw_ts)
                except ValueError:
                    last_ingested = None

        return MemoryStats(
            total_entities=int(entities_res.records[0]["cnt"]) if entities_res.records else 0,
            total_relations=int(relations_res.records[0]["cnt"]) if relations_res.records else 0,
            total_episodes=int(episodes_res.records[0]["cnt"]) if episodes_res.records else 0,
            last_ingestion_at=last_ingested,
        )

    def _map_results_to_facts(self, results: list[Any]) -> list[MemoryFact]:
        """Map Graphiti search results to MemoryFact domain models."""
        facts: list[MemoryFact] = []
        for edge in results:
            fact_text = getattr(edge, "fact", None) or getattr(edge, "name", None)
            facts.append(
                MemoryFact(
                    fact_text=str(fact_text) if fact_text else str(edge),
                    subject_name=getattr(edge, "name", None),
                    confidence=1.0,
                    created_at=getattr(edge, "created_at", None),
                    valid_at=getattr(edge, "valid_at", None),
                    reference_time=getattr(edge, "reference_time", None),
                )
            )
        return facts
