"""Graphiti memory backend implementation."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from graphiti_core import Graphiti
from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig
from graphiti_core.llm_client.config import LLMConfig
from graphiti_core.llm_client.openai_client import OpenAIClient
from graphiti_core.nodes import EpisodeType
from pydantic import BaseModel, Field
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from bot.domain.models import MemoryFact, MemoryStats
from bot.interfaces import MemoryBackend
from bot.log import get_logger

logger = get_logger(__name__)


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
        """Close connections."""
        # Clean up neo4j driver if possible
        if hasattr(self.client, "close"):
            await self.client.close()

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type(
            Exception
        ),  # Replace with Neo4j specific transient exceptions if known
        reraise=True,
    )
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

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    async def search_quick(
        self, user_name: str, group_id: str, *, limit: int = 5
    ) -> list[MemoryFact]:
        """Perform a quick search for user facts."""
        query = f"Key facts about {user_name}"
        results = await self.client.search(
            query=query,
            group_ids=[group_id],
            num_results=limit,
        )

        return self._map_results_to_facts(results)

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    async def search_deep(self, query: str, group_id: str, *, limit: int = 10) -> list[MemoryFact]:
        """Perform a deep semantic search."""
        results = await self.client.search(
            query=query,
            group_ids=[group_id],
            num_results=limit,
        )

        return self._map_results_to_facts(results)

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    async def delete_facts(self, description: str, group_id: str) -> int:
        """Delete facts matching the description."""
        results = await self.client.search(
            query=description,
            group_ids=[group_id],
            num_results=5,
        )

        edges = results if isinstance(results, list) else getattr(results, "edges", [])
        uuids = [getattr(e, "uuid", None) for e in edges if getattr(e, "uuid", None)]
        if not uuids:
            return 0

        res = await self.client.driver.execute_query(
            "MATCH ()-[r]->() WHERE r.uuid IN $uuids DELETE r RETURN count(r) as cnt",
            params={"uuids": uuids},
        )
        if res.records:
            return int(res.records[0]["cnt"])
        return len(uuids)

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
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
            "MATCH (e:Episode) WHERE e.group_id = $group_id "
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
                except Exception:
                    last_ingested = None

        return MemoryStats(
            total_entities=int(entities_res.records[0]["cnt"]) if entities_res.records else 0,
            total_relations=int(relations_res.records[0]["cnt"]) if relations_res.records else 0,
            total_episodes=int(episodes_res.records[0]["cnt"]) if episodes_res.records else 0,
            last_ingestion_at=last_ingested,
        )

    def _map_results_to_facts(self, results: Any) -> list[MemoryFact]:
        """Map Graphiti search results to MemoryFact domain models."""
        facts = []
        edges = results if isinstance(results, list) else getattr(results, "edges", [])
        for edge in edges:
            fact_text = getattr(edge, "fact", None) or getattr(edge, "name", str(edge))
            source_node = getattr(edge, "source_node", None)
            subject_name = (
                getattr(source_node, "name", None) if source_node else getattr(edge, "name", None)
            )

            facts.append(
                MemoryFact(
                    fact_text=fact_text,
                    subject_name=subject_name,
                    confidence=1.0,
                    created_at=getattr(edge, "created_at", None),
                )
            )

        return facts
