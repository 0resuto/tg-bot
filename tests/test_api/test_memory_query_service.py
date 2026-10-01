"""Tests for MemoryQueryService: fact fetching scoping and stats aggregation."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.api.services.memory_query_service import MemoryQueryService
from bot.config import Settings
from bot.models import MemoryStats


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


_FACTS = [
    {"subject": "Alice", "fact": "likes coffee", "created_at": None},
    {"subject": "Bob", "fact": "visiting Rome", "created_at": "2026-09-01T10:00:00+00:00"},
]


@pytest.mark.asyncio
async def test_get_memories_scopes_by_chat_id():
    captured: dict[str, object] = {}
    driver = _FakeDriver(_FACTS, captured)
    service = MemoryQueryService(_settings(), memory_service=None, driver=driver)

    facts = await service.get_memories(chat_id=123)

    assert "r.group_id = $group_id" in str(captured["query"])
    assert captured["params"] == {"group_id": "123"}
    assert captured.get("closed") is None
    assert [fact["subject"] for fact in facts] == ["Alice", "Bob"]
    assert facts[0]["fact_text"] == "likes coffee"


@pytest.mark.asyncio
async def test_get_memories_without_chat_id_is_unscoped():
    captured: dict[str, object] = {}
    driver = _FakeDriver(_FACTS, captured)
    service = MemoryQueryService(_settings(), memory_service=None, driver=driver)

    facts = await service.get_memories(chat_id=None)

    assert captured["params"] == {}
    assert len(facts) == 2


@pytest.mark.asyncio
async def test_get_memories_without_password_returns_empty():
    service = MemoryQueryService(_settings(neo4j_password=""), memory_service=None)

    assert await service.get_memories(chat_id=1) == []


@pytest.mark.asyncio
async def test_get_memories_closes_self_created_driver():
    captured: dict[str, object] = {}
    driver = _FakeDriver(_FACTS, captured)

    with patch("bot.api.services.memory_query_service.AsyncGraphDatabase") as async_db:
        async_db.driver.return_value = driver
        service = MemoryQueryService(_settings(), memory_service=None)
        await service.get_memories(chat_id=1)

    assert captured["closed"] is True


@pytest.mark.asyncio
async def test_get_stats_offline_without_memory_service():
    service = MemoryQueryService(_settings(), memory_service=None)

    result = await service.get_stats(chat_id=1)

    assert result == {"memory_stats": {"status": "offline"}}


@pytest.mark.asyncio
async def test_get_stats_aggregates_memory_service_metrics():
    memory_service = MagicMock()
    memory_service.get_stats = AsyncMock(
        return_value=MemoryStats(
            total_entities=3,
            total_relations=4,
            total_episodes=5,
            last_ingestion_at=datetime(2026, 9, 1, 12, 0, tzinfo=UTC),
        )
    )
    service = MemoryQueryService(_settings(), memory_service=memory_service)

    result = await service.get_stats(chat_id=42)

    assert result["memory_stats"]["total_entities"] == 3
    assert result["memory_stats"]["total_relations"] == 4
    assert result["memory_stats"]["total_episodes"] == 5
    assert (
        result["memory_stats"]["last_ingestion_at"]
        == datetime(2026, 9, 1, 12, 0, tzinfo=UTC).isoformat()
    )
    memory_service.get_stats.assert_awaited_once_with(42)


@pytest.mark.asyncio
async def test_get_stats_reports_errors():
    memory_service = MagicMock()
    memory_service.get_stats = AsyncMock(side_effect=RuntimeError("boom"))
    service = MemoryQueryService(_settings(), memory_service=memory_service)

    result = await service.get_stats(chat_id=1)

    assert result["memory_stats"]["status"] == "error"
    assert "boom" in result["memory_stats"]["error"]
