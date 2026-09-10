"""Token usage repository implementation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.domain.models import TokenUsageRecord
from bot.infrastructure.database.tables import TokenUsageORM


class TokenUsageRepository:
    """Repository for managing token usage tracking."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self.session_factory = session_factory

    async def record_usage(self, record: TokenUsageRecord) -> None:
        """Record a single token usage event."""
        async with self.session_factory() as session:
            orm_record = TokenUsageORM(
                chat_id=record.chat_id,
                telegram_user_id=record.telegram_user_id,
                model=record.model,
                prompt_tokens=record.prompt_tokens,
                completion_tokens=record.completion_tokens,
                total_tokens=record.total_tokens,
                operation=record.operation.value,
                created_at=record.timestamp,
            )
            session.add(orm_record)
            await session.commit()

    async def get_usage_stats(self, chat_id: int, days: int = 30) -> dict:
        """Get aggregated token usage statistics."""
        now = datetime.now(UTC)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=today_start.weekday())
        month_start = today_start.replace(day=1)

        async with self.session_factory() as session:
            # Helper to get sum for a date range
            async def get_sum(start_date: datetime) -> int:
                stmt = select(func.sum(TokenUsageORM.total_tokens)).where(
                    TokenUsageORM.chat_id == chat_id, TokenUsageORM.created_at >= start_date
                )
                result = await session.execute(stmt)
                return result.scalar() or 0

            today_tokens = await get_sum(today_start)
            week_tokens = await get_sum(week_start)
            month_tokens = await get_sum(month_start)

            # Get breakdown by operation for the requested days period
            period_start = now - timedelta(days=days)
            stmt = (
                select(TokenUsageORM.operation, func.sum(TokenUsageORM.total_tokens))
                .where(TokenUsageORM.chat_id == chat_id, TokenUsageORM.created_at >= period_start)
                .group_by(TokenUsageORM.operation)
            )
            result = await session.execute(stmt)
            by_operation = {row[0]: row[1] for row in result.all()}

            return {
                "today_tokens": today_tokens,
                "week_tokens": week_tokens,
                "month_tokens": month_tokens,
                "by_operation": by_operation,
            }

    async def get_daily_usage(self, chat_id: int, days: int = 30) -> list[dict]:
        """Get daily breakdown of token usage."""
        period_start = datetime.now(UTC) - timedelta(days=days)

        async with self.session_factory() as session:
            date_expr = func.date(TokenUsageORM.created_at).label("day")
            stmt = (
                select(date_expr, func.sum(TokenUsageORM.total_tokens).label("tokens"))
                .where(TokenUsageORM.chat_id == chat_id, TokenUsageORM.created_at >= period_start)
                .group_by(date_expr)
                .order_by(date_expr)
            )
            result = await session.execute(stmt)

            return [{"date": str(row.day), "tokens": row.tokens} for row in result.all()]
