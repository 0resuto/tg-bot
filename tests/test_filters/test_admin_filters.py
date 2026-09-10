from __future__ import annotations

from bot.telegram.filters.admin import IsAdminChat, IsAdminUser


class MockChat:
    def __init__(self, id):
        self.id = id


class MockUser:
    def __init__(self, id):
        self.id = id


class MockMessage:
    def __init__(self, chat_id, user_id=None):
        self.chat = MockChat(chat_id)
        if user_id:
            self.from_user = MockUser(user_id)
        else:
            self.from_user = None


async def test_is_admin_chat():
    filter_instance = IsAdminChat(admin_chat_id=1)
    assert await filter_instance(MockMessage(chat_id=1)) is True
    assert await filter_instance(MockMessage(chat_id=3)) is False


async def test_is_admin_user():
    filter_instance = IsAdminUser(admin_user_id=10)
    assert await filter_instance(MockMessage(chat_id=1, user_id=10)) is True
    assert await filter_instance(MockMessage(chat_id=1, user_id=30)) is False
    assert await filter_instance(MockMessage(chat_id=1)) is False
