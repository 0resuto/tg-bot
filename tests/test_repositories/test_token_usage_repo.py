from __future__ import annotations

from datetime import datetime

from bot.domain.enums import OperationType
from bot.domain.models import TokenUsageRecord
from bot.repositories.token_usage_repo import TokenUsageRepository


async def test_record_usage(db_session):
    repo = TokenUsageRepository(db_session)
    record = TokenUsageRecord(
        chat_id=1,
        model="test-model",
        prompt_tokens=10,
        completion_tokens=5,
        total_tokens=15,
        operation=OperationType.RESPONSE,
        telegram_user_id=10,
        timestamp=datetime.now(),
    )
    await repo.record_usage(record)

    stats = await repo.get_usage_stats(1, 30)
    assert stats is not None


async def test_concurrent_record_usage(db_session):
    import asyncio

    repo = TokenUsageRepository(db_session)
    records = [
        TokenUsageRecord(
            chat_id=777,
            model="test-model",
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            operation=OperationType.RESPONSE,
            telegram_user_id=1,
            timestamp=datetime.now(),
        )
        for _ in range(10)
    ]
    await asyncio.gather(*(repo.record_usage(r, chat_title="Chat 777") for r in records))
    stats = await repo.get_usage_stats(777, 30)
    assert stats["today_tokens"] == 150
