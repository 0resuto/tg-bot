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


def _make_edge(fact: str, valid_at: datetime | None, reference_time: datetime | None):
    edge = MagicMock()
    edge.fact = fact
    edge.name = "RELATES_TO"
    edge.created_at = datetime(2026, 10, 5, tzinfo=UTC)
    edge.valid_at = valid_at
    edge.reference_time = reference_time
    return edge


@pytest.mark.asyncio
async def test_search_deep_applies_window_server_side():
    """A time window must be sent to Graphiti as a server-side valid_at filter."""
    from graphiti_core.search.search_filters import ComparisonOperator

    backend = GraphitiMemoryBackend.__new__(GraphitiMemoryBackend)
    in_range = _make_edge("in range", datetime(2026, 9, 30, tzinfo=UTC), None)
    out_of_range = _make_edge("too old", datetime(2026, 1, 1, tzinfo=UTC), None)

    client = MagicMock()
    client.search = AsyncMock(return_value=[in_range, out_of_range])
    backend.client = client

    window = (
        datetime(2026, 9, 28, 21, 0, tzinfo=UTC),
        datetime(2026, 10, 5, 21, 0, tzinfo=UTC),
    )
    facts = await backend.search_deep("summary", "-100", limit=5, valid_at_range=window)

    assert [f.fact_text for f in facts] == ["in range"]
    first_call = client.search.await_args_list[0].kwargs
    assert first_call["num_results"] == 5
    date_filters = first_call["search_filter"].valid_at[0]
    assert date_filters[0].date == window[0]
    assert date_filters[0].comparison_operator == ComparisonOperator.greater_than_equal
    assert date_filters[1].date == window[1]
    assert date_filters[1].comparison_operator == ComparisonOperator.less_than


@pytest.mark.asyncio
async def test_search_deep_tops_up_undated_facts_by_reference_time():
    """Facts without valid_at are recovered via a second query and reference_time."""
    backend = GraphitiMemoryBackend.__new__(GraphitiMemoryBackend)
    fallback = _make_edge("mentioned last week", None, datetime(2026, 10, 1, tzinfo=UTC))
    too_old = _make_edge("old mention", None, datetime(2026, 1, 1, tzinfo=UTC))

    client = MagicMock()
    client.search = AsyncMock(side_effect=[[], [fallback, too_old]])
    backend.client = client

    window = (
        datetime(2026, 9, 28, 21, 0, tzinfo=UTC),
        datetime(2026, 10, 5, 21, 0, tzinfo=UTC),
    )
    facts = await backend.search_deep("summary", "-100", limit=5, valid_at_range=window)

    assert [f.fact_text for f in facts] == ["mentioned last week"]
    assert client.search.await_count == 2
    assert client.search.await_args_list[1].kwargs["num_results"] == 20
    assert "search_filter" not in client.search.await_args_list[1].kwargs


@pytest.mark.asyncio
async def test_search_deep_without_window_maps_times():
    """Without a window no filtering happens; valid_at/reference_time are mapped."""
    backend = GraphitiMemoryBackend.__new__(GraphitiMemoryBackend)

    edge = MagicMock()
    edge.fact = "Alice bought a bike"
    edge.name = "BOUGHT"
    edge.created_at = datetime(2026, 10, 5, tzinfo=UTC)
    edge.valid_at = datetime(2026, 9, 30, tzinfo=UTC)
    edge.reference_time = datetime(2026, 9, 29, tzinfo=UTC)

    client = MagicMock()
    client.search = AsyncMock(return_value=[edge])
    backend.client = client

    facts = await backend.search_deep("bike", "-100", limit=5)

    assert len(facts) == 1
    assert facts[0].valid_at == datetime(2026, 9, 30, tzinfo=UTC)
    assert facts[0].reference_time == datetime(2026, 9, 29, tzinfo=UTC)
    assert client.search.await_args.kwargs["num_results"] == 5


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
