from __future__ import annotations

from bot.telegram.filters.admin import IsAdminChat, IsAdminUser, IsGroupChat


class MockChat:
    def __init__(self, id):
        self.id = id


class MockUser:
    def __init__(self, id):
        self.id = id


class MockMessage:
    def __init__(self, chat_id, user_id=None):
        self.chat = MockChat(chat_id) if chat_id is not None else None
        if user_id:
            self.from_user = MockUser(user_id)
        else:
            self.from_user = None


async def test_is_admin_chat():
    filter_instance = IsAdminChat(admin_chat_id=1)
    assert await filter_instance(MockMessage(chat_id=1)) is True
    assert await filter_instance(MockMessage(chat_id=3)) is False
    assert await filter_instance(MockMessage(chat_id=None)) is False

    # Unconfigured admin_chat_id (0) must reject all
    filter_unconfigured = IsAdminChat(admin_chat_id=0)
    assert await filter_unconfigured(MockMessage(chat_id=0)) is False
    assert await filter_unconfigured(MockMessage(chat_id=1)) is False
    assert await filter_unconfigured(MockMessage(chat_id=None)) is False


async def test_is_admin_user():
    filter_instance = IsAdminUser(admin_user_id=10)
    assert await filter_instance(MockMessage(chat_id=1, user_id=10)) is True
    assert await filter_instance(MockMessage(chat_id=1, user_id=30)) is False
    assert await filter_instance(MockMessage(chat_id=1)) is False

    # Multi-admin set support (admin_user_id and admin_chat_id)
    multi_filter = IsAdminUser(admin_user_id={10, 20})
    assert await multi_filter(MockMessage(chat_id=1, user_id=10)) is True
    assert await multi_filter(MockMessage(chat_id=1, user_id=20)) is True
    assert await multi_filter(MockMessage(chat_id=1, user_id=30)) is False

    # Unconfigured admin_user_id (0 or empty set) must reject all
    unconfigured = IsAdminUser(admin_user_id=0)
    assert await unconfigured(MockMessage(chat_id=1, user_id=0)) is False
    assert await unconfigured(MockMessage(chat_id=1, user_id=10)) is False


async def test_is_group_chat():
    filter_instance = IsGroupChat(group_chat_id=-100123)
    assert await filter_instance(MockMessage(chat_id=-100123)) is True
    assert await filter_instance(MockMessage(chat_id=-100999)) is False
    assert await filter_instance(MockMessage(chat_id=123)) is False
    assert await filter_instance(MockMessage(chat_id=None)) is False

    # Unconfigured group_chat_id (0) must reject all
    filter_unconfigured = IsGroupChat(group_chat_id=0)
    assert await filter_unconfigured(MockMessage(chat_id=0)) is False
    assert await filter_unconfigured(MockMessage(chat_id=-100123)) is False
    assert await filter_unconfigured(MockMessage(chat_id=None)) is False
