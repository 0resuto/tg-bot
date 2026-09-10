from __future__ import annotations

from bot.repositories.chat_repo import ChatRepository


async def test_upsert_chat_new(db_session):
    repo = ChatRepository(db_session)
    await repo.upsert_chat(1, "Test Chat")

    active = await repo.get_active_chat_ids()
    assert 1 in active


async def test_upsert_chat_update(db_session):
    repo = ChatRepository(db_session)
    await repo.upsert_chat(1, "Test Chat")
    await repo.upsert_chat(1, "Updated Chat")

    active = await repo.get_active_chat_ids()
    assert 1 in active
