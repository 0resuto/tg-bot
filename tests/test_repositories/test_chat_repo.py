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


async def test_concurrent_upsert_chat(db_session):
    import asyncio

    repo = ChatRepository(db_session)
    # Run concurrent upserts on the same new chat
    await asyncio.gather(*(repo.upsert_chat(999, f"Title {i}") for i in range(10)))

    chat = await repo.get_chat(999)
    assert chat is not None
    assert chat.chat_id == 999
