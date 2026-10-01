"""Tests for GraphitiMemoryBackend lifecycle and error handling."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from bot.db.graphiti import GraphitiMemoryBackend


@pytest.mark.asyncio
async def test_graphiti_backend_close_lifecycle():
    """Verify close() gracefully closes client and driver resources."""
    backend = GraphitiMemoryBackend.__new__(GraphitiMemoryBackend)
    mock_driver = MagicMock()
    mock_driver.close = AsyncMock()

    mock_client = MagicMock()
    mock_client.close = AsyncMock()
    mock_client.driver = mock_driver
    backend.client = mock_client

    await backend.close()
    mock_client.close.assert_awaited_once()
    mock_driver.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_stats_counts_episodic_nodes():
    """get_stats must count Graphiti episodic nodes (label :Episodic) with timestamps."""
    backend = GraphitiMemoryBackend.__new__(GraphitiMemoryBackend)

    entities = MagicMock(records=[{"cnt": 3}])
    relations = MagicMock(records=[{"cnt": 4}])
    episodes = MagicMock(records=[{"cnt": 2, "last_ingested": "2026-09-01T10:00:00+00:00"}])

    driver = MagicMock()
    driver.execute_query = AsyncMock(side_effect=[entities, relations, episodes])
    client = MagicMock()
    client.driver = driver
    backend.client = client

    stats = await backend.get_stats(group_id="-100")

    assert stats.total_entities == 3
    assert stats.total_relations == 4
    assert stats.total_episodes == 2
    assert stats.last_ingestion_at == datetime(2026, 9, 1, 10, 0, tzinfo=UTC)

    queries = [call.args[0] for call in driver.execute_query.await_args_list]
    assert any("MATCH (e:Episodic)" in query for query in queries)
    assert not any("MATCH (e:Episode)" in query for query in queries)
    assert all(
        call.kwargs["params"] == {"group_id": "-100"}
        for call in driver.execute_query.await_args_list
    )


def test_graphiti_entity_node_schemas():
    """Verify custom graph node entity schemas define correct domain attributes."""
    from bot.db.graphiti import (
        DEFAULT_ENTITY_TYPES,
        Animal,
        Concept,
        Item,
        Location,
        Person,
    )

    p = Person(role="Admin")
    assert p.role == "Admin"

    a = Animal(species="Cat")
    assert a.species == "Cat"

    i = Item(category="Vehicle")
    assert i.category == "Vehicle"

    loc = Location()
    assert isinstance(loc, Location)

    c = Concept()
    assert isinstance(c, Concept)

    assert DEFAULT_ENTITY_TYPES["Person"] is Person
    assert DEFAULT_ENTITY_TYPES["Animal"] is Animal
    assert DEFAULT_ENTITY_TYPES["Item"] is Item
    assert DEFAULT_ENTITY_TYPES["Location"] is Location
    assert DEFAULT_ENTITY_TYPES["Concept"] is Concept
