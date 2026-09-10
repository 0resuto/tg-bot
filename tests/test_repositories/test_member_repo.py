from __future__ import annotations

from bot.domain.models import MemberIdentity
from bot.repositories.member_repo import MemberRepository


async def test_upsert_member_new(db_session):
    repo = MemberRepository(db_session)
    member = MemberIdentity(10, "alice", "Alice", None)
    await repo.upsert_member(1, member)

    m = await repo.get_member(1, 10)
    assert m is not None
    assert m.username == "alice"


async def test_upsert_member_update(db_session):
    repo = MemberRepository(db_session)
    member1 = MemberIdentity(10, "alice", "Alice", None)
    await repo.upsert_member(1, member1)

    member2 = MemberIdentity(10, "alice_new", "Alice", None)
    await repo.upsert_member(1, member2)

    m = await repo.get_member(1, 10)
    assert m.username == "alice_new"
