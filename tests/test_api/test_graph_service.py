"""Tests for GraphVisualizerService: Cypher scoping, node classification, serialization."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from bot.api.services.graph_service import GraphVisualizerService, _serialize_neo4j_val
from bot.config import Settings


class _FakeNode:
    def __init__(self, element_id: str, labels: list[str], props: dict[str, object]) -> None:
        self.element_id = element_id
        self.labels = set(labels)
        self._props = props

    def keys(self) -> object:
        return self._props.keys()

    def __getitem__(self, key: str) -> object:
        return self._props[key]

    def items(self) -> object:
        return self._props.items()


class _FakeRel(_FakeNode):
    def __init__(self, element_id: str, rel_type: str, props: dict[str, object]) -> None:
        super().__init__(element_id, [], props)
        self.type = rel_type


class _FakeResult:
    def __init__(self, records: list[dict[str, object]]) -> None:
        self._records = records

    def __aiter__(self) -> object:
        return self._generator()

    async def _generator(self):  # type: ignore[no-untyped-def]
        for record in self._records:
            yield record


class _FakeSession:
    def __init__(self, records: list[dict[str, object]], captured: dict[str, object]) -> None:
        self._records = records
        self._captured = captured

    async def __aenter__(self) -> _FakeSession:
        return self

    async def __aexit__(self, *args: object) -> bool:
        return False

    async def run(self, query: str, params: dict[str, object] | None = None) -> _FakeResult:
        self._captured["query"] = query
        self._captured["params"] = params or {}
        return _FakeResult(self._records)


class _FakeDriver:
    def __init__(self, records: list[dict[str, object]], captured: dict[str, object]) -> None:
        self._records = records
        self._captured = captured

    def session(self) -> _FakeSession:
        self._captured["session_calls"] = int(self._captured.get("session_calls", 0)) + 1
        return _FakeSession(self._records, self._captured)

    async def close(self) -> None:
        self._captured["closed"] = True


def _settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "_env_file": None,
        "neo4j_uri": "bolt://fake:7687",
        "neo4j_user": "neo4j",
        "neo4j_password": "neo-pass",
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


def _sample_records() -> list[dict[str, object]]:
    n = _FakeNode("n1", ["Person"], {"name": "Alice"})
    m = _FakeNode("m1", ["Concept"], {"name": "Coffee"})
    rel = _FakeRel("r1", "RELATES_TO", {"fact": "Alice likes coffee"})
    return [{"n": n, "r": rel, "m": m}]


def test_serialize_neo4j_val_converts_nested_values():
    moment = datetime(2026, 9, 29, 12, 0, tzinfo=UTC)
    assert _serialize_neo4j_val(None) is None
    assert _serialize_neo4j_val(5) == 5
    assert _serialize_neo4j_val(moment) == str(moment)
    assert _serialize_neo4j_val({"a": [moment]}) == {"a": [str(moment)]}


def test_classify_node_maps_all_categories():
    service = GraphVisualizerService(_settings())
    cases = [
        (["Episodic"], "Episodic"),
        (["Community"], "Community"),
        (["Person"], "Person"),
        (["Animal"], "Animal"),
        (["Item"], "Item"),
        (["Location"], "Location"),
        (["Concept"], "Concept"),
        (["Unknown"], "Entity"),
    ]
    for labels, expected in cases:
        meta = service._classify_node(labels, {"name": "X"})
        assert meta["group"] == expected


def test_classify_node_truncates_long_names():
    service = GraphVisualizerService(_settings())
    meta = service._classify_node(["Person"], {"name": "A" * 40})
    assert meta["display_label"] == "A" * 21 + "..."
    assert meta["full_name"] == "A" * 40


@pytest.mark.asyncio
async def test_fetch_graph_data_scopes_by_chat_id():
    captured: dict[str, object] = {}
    driver = _FakeDriver(_sample_records(), captured)
    service = GraphVisualizerService(_settings(), driver=driver)

    nodes, edges = await service.fetch_graph_data(chat_id=123)

    assert "n.group_id = $group_id" in str(captured["query"])
    assert captured["params"] == {"group_id": "123"}
    assert captured.get("closed") is None

    assert {node["id"] for node in nodes} == {"n1", "m1"}
    person = next(node for node in nodes if node["id"] == "n1")
    assert person["group"] == "Person"
    assert person["properties"]["name"] == "Alice"

    assert len(edges) == 1
    assert edges[0]["from"] == "n1"
    assert edges[0]["to"] == "m1"
    assert edges[0]["type"] == "RELATES_TO"
    assert edges[0]["full_fact"] == "Alice likes coffee"


@pytest.mark.asyncio
async def test_fetch_graph_data_without_chat_id_is_unscoped():
    captured: dict[str, object] = {}
    driver = _FakeDriver(_sample_records(), captured)
    service = GraphVisualizerService(_settings(), driver=driver)

    nodes, _ = await service.fetch_graph_data(chat_id=None)

    assert captured["params"] == {}
    assert "group_id" not in str(captured["query"])
    assert len(nodes) == 2


@pytest.mark.asyncio
async def test_fetch_graph_data_without_password_returns_empty():
    captured: dict[str, object] = {}
    driver = _FakeDriver(_sample_records(), captured)
    service = GraphVisualizerService(_settings(neo4j_password=""), driver=driver)

    assert await service.fetch_graph_data(chat_id=1) == ([], [])
    assert "session_calls" not in captured


@pytest.mark.asyncio
async def test_fetch_graph_data_closes_self_created_driver():
    captured: dict[str, object] = {}
    driver = _FakeDriver(_sample_records(), captured)

    with patch("bot.api.services.graph_service.AsyncGraphDatabase") as async_db:
        async_db.driver.return_value = driver
        service = GraphVisualizerService(_settings())
        await service.fetch_graph_data(chat_id=1)

    assert captured["closed"] is True
