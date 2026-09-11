"""Chat repository implementation."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.infrastructure.database.tables import ChatORM


class ChatRepository:
    """Repository for managing chats."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self.session_factory = session_factory

    async def get_active_chat_ids(self) -> list[int]:
        """Get IDs of all active chats."""
        async with self.session_factory() as session:
            stmt = select(ChatORM.chat_id).where(ChatORM.is_active.is_(True))
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_chat(self, chat_id: int) -> ChatORM | None:
        """Get a chat by its ID."""
        async with self.session_factory() as session:
            stmt = select(ChatORM).where(ChatORM.chat_id == chat_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def upsert_chat(self, chat_id: int, title: str | None = None) -> None:
        """Upsert a chat atomically, updating its title if provided."""
        async with self.session_factory() as session:
            values: dict[str, Any] = {"chat_id": chat_id, "title": title}
            update_set: dict[str, Any] = {"is_active": True}
            if title is not None:
                update_set["title"] = title

            stmt = (
                insert(ChatORM)
                .values(**values)
                .on_conflict_do_update(
                    index_elements=[ChatORM.chat_id],
                    set_=update_set,
                )
            )
            await session.execute(stmt)
            await session.commit()
