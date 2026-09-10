"""Graphiti memory backend implementation."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

import structlog
from graphiti_core import Graphiti
from graphiti_core.nodes import EpisodeType
from pydantic import BaseModel, Field
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from bot.domain.models import MemoryFact
from bot.interfaces import MemoryBackend

logger = structlog.get_logger()


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
        self.neo4j_uri = neo4j_uri
        self.neo4j_user = neo4j_user
        self.neo4j_password = neo4j_password
        self.entity_types = entity_types if entity_types is not None else DEFAULT_ENTITY_TYPES

        # Configure Graphiti
        import os

        os.environ["OPENAI_API_KEY"] = openai_api_key
        os.environ["NEO4J_URI"] = neo4j_uri
        os.environ["NEO4J_USERNAME"] = neo4j_user
        os.environ["NEO4J_PASSWORD"] = neo4j_password

        # Additional settings for extraction / embedding could be set here
        # or passed if graphiti exposes them directly in its Client

        self.client = Graphiti(
            uri=neo4j_uri,
            user=neo4j_user,
            password=neo4j_password,
        )
        self.is_initialized = False

    async def init(self) -> None:
        """Initialize the Graphiti client connections."""
        # Typically Graphiti async setup would go here.
        # graphiti_core handles neo4j connections.
        self.is_initialized = True

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
        import asyncio

        from neo4j import GraphDatabase

        results = await self.client.search(
            query=description,
            group_ids=[group_id],
            num_results=5,
        )

        edges = results if isinstance(results, list) else getattr(results, "edges", [])
        uuids = [getattr(e, "uuid", None) for e in edges if getattr(e, "uuid", None)]
        if not uuids:
            return 0

        def _delete() -> int:
            driver = GraphDatabase.driver(
                self.neo4j_uri, auth=(self.neo4j_user, self.neo4j_password)
            )
            try:
                with driver.session() as session:
                    res = session.run(
                        "MATCH ()-[r]->() WHERE r.uuid IN $uuids DELETE r RETURN count(r) as cnt",
                        {"uuids": uuids},
                    ).single()
                    return int(res["cnt"]) if res else len(uuids)
            finally:
                driver.close()

        return await asyncio.to_thread(_delete)

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    async def get_stats(self, group_id: str) -> dict[str, Any]:
        """Get graph statistics for the given group."""
        import asyncio

        from neo4j import GraphDatabase

        def _fetch_stats() -> dict[str, Any]:
            driver = GraphDatabase.driver(
                self.neo4j_uri, auth=(self.neo4j_user, self.neo4j_password)
            )
            try:
                with driver.session() as session:
                    nodes_res = session.run("MATCH (n) RETURN count(n) as cnt").single()
                    edges_res = session.run("MATCH ()-[r]->() RETURN count(r) as cnt").single()
                    return {
                        "group_id": group_id,
                        "nodes": int(nodes_res["cnt"]) if nodes_res else 0,
                        "edges": int(edges_res["cnt"]) if edges_res else 0,
                    }
            finally:
                driver.close()

        return await asyncio.to_thread(_fetch_stats)

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
