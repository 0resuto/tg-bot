from __future__ import annotations

from datetime import datetime

import pytest

from bot.domain.enums import OperationType
from bot.domain.models import MemoryFact, TokenUsageRecord


class MockLLMProvider:
    def __init__(self):
        self.calls = []
        self.response_text = "Mock response"

    async def generate_response(
        self, system_prompt, messages, *, model=None, temperature=0.7, max_tokens=1024
    ):
        self.calls.append({"system_prompt": system_prompt, "messages": messages, "model": model})
        usage = TokenUsageRecord(
            chat_id=0,
            model=model or "test-model",
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            operation=OperationType.RESPONSE,
            telegram_user_id=None,
            timestamp=datetime.now(),
        )
        return self.response_text, usage


class MockMemoryBackend:
    def __init__(self):
        self.episodes = []
        self.facts = [
            MemoryFact(
                fact_text="likes coffee", subject_name="Alice", confidence=0.9, created_at=None
            )
        ]

    async def ingest_episode(self, text, group_id, source_user_name, reference_time):
        self.episodes.append({"text": text, "group_id": group_id})

    async def search_quick(self, user_name, group_id, *, limit=5):
        return [f for f in self.facts if f.subject_name == user_name][:limit]

    async def search_deep(self, query, group_id, *, limit=15):
        return self.facts[:limit]

    async def delete_facts(self, description, group_id):
        before = len(self.facts)
        self.facts = [f for f in self.facts if description.lower() not in f.fact_text.lower()]
        return before - len(self.facts)

    async def get_stats(self, group_id):
        return {"total_entities": 5, "total_relations": 10, "total_episodes": 3}


class MockTokenUsageRepo:
    def __init__(self):
        self.records = []

    async def record_usage(self, record):
        self.records.append(record)

    async def get_usage_stats(self, chat_id, days=30):
        return {"today_tokens": 100, "week_tokens": 500, "month_tokens": 2000}


@pytest.fixture
def fake_redis():
    import fakeredis.aioredis

    return fakeredis.aioredis.FakeRedis()


@pytest.fixture
async def db_session():
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from bot.infrastructure.database.tables import Base

    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    yield session_factory

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
