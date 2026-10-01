"""Member repository implementation."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.db.tables import ChatMemberORM, ChatORM
from bot.models import MemberIdentity


class MemberRepository:
    """Repository for managing chat members."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self.session_factory = session_factory

    async def upsert_member(
        self, chat_id: int, member: MemberIdentity, chat_title: str | None = None
    ) -> None:
        """Upsert a member and ensure chat exists."""
        async with self.session_factory() as session:
            # Ensure chat exists atomically to satisfy Foreign Key constraint
            chat_stmt = insert(ChatORM).values(chat_id=chat_id, title=chat_title)
            if chat_title is not None:
                chat_stmt = chat_stmt.on_conflict_do_update(
                    index_elements=[ChatORM.chat_id],
                    set_={"title": chat_title},
                )
            else:
                chat_stmt = chat_stmt.on_conflict_do_nothing(
                    index_elements=[ChatORM.chat_id],
                )
            await session.execute(chat_stmt)

            # Atomic upsert for member record
            member_stmt = (
                insert(ChatMemberORM)
                .values(
                    telegram_user_id=member.telegram_user_id,
                    chat_id=chat_id,
                    username=member.username,
                    first_name=member.first_name,
                    last_name=member.last_name,
                    display_name=member.display_name,
                )
                .on_conflict_do_update(
                    index_elements=["telegram_user_id", "chat_id"],
                    set_={
                        "username": member.username,
                        "first_name": member.first_name,
                        "last_name": member.last_name,
                        "display_name": member.display_name,
                    },
                )
            )
            await session.execute(member_stmt)
            await session.commit()

    async def get_member(self, chat_id: int, telegram_user_id: int) -> MemberIdentity | None:
        """Get a member by chat ID and telegram user ID."""
        async with self.session_factory() as session:
            stmt = select(ChatMemberORM).where(
                ChatMemberORM.chat_id == chat_id, ChatMemberORM.telegram_user_id == telegram_user_id
            )
            result = await session.execute(stmt)
            orm_member = result.scalar_one_or_none()

            if not orm_member:
                return None

            return MemberIdentity(
                telegram_user_id=orm_member.telegram_user_id,
                username=orm_member.username,
                first_name=orm_member.first_name,
                last_name=orm_member.last_name,
            )

    async def get_members_by_chat(self, chat_id: int) -> list[MemberIdentity]:
        """Get all members for a specific chat."""
        async with self.session_factory() as session:
            stmt = select(ChatMemberORM).where(ChatMemberORM.chat_id == chat_id)
            result = await session.execute(stmt)
            orm_members = result.scalars().all()

            return [
                MemberIdentity(
                    telegram_user_id=m.telegram_user_id,
                    username=m.username,
                    first_name=m.first_name,
                    last_name=m.last_name,
                )
                for m in orm_members
            ]
