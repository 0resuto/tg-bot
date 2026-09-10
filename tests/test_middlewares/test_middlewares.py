from __future__ import annotations

from bot.telegram.middlewares.allowlist import ChatAllowlistMiddleware
from bot.telegram.middlewares.services import ServicesMiddleware


class MockChat:
    def __init__(self, chat_id: int):
        self.id = chat_id


class MockUpdate:
    pass


async def test_allowlist_middleware_allowed():
    middleware = ChatAllowlistMiddleware(allowed_chat_ids={123, 456})

    called = False

    async def dummy_handler(event, data):
        nonlocal called
        called = True
        return "ok"

    data = {"event_chat": MockChat(123)}
    result = await middleware(dummy_handler, MockUpdate(), data)
    assert called is True
    assert result == "ok"


async def test_allowlist_middleware_denied():
    middleware = ChatAllowlistMiddleware(allowed_chat_ids={123})

    called = False

    async def dummy_handler(event, data):
        nonlocal called
        called = True
        return "ok"

    data = {"event_chat": MockChat(999)}
    result = await middleware(dummy_handler, MockUpdate(), data)
    assert called is False
    assert result is None


async def test_allowlist_update():
    middleware = ChatAllowlistMiddleware(allowed_chat_ids={123})
    middleware.update_allowed_chats({123, 999})

    called = False

    async def dummy_handler(event, data):
        nonlocal called
        called = True
        return "ok"

    data = {"event_chat": MockChat(999)}
    result = await middleware(dummy_handler, MockUpdate(), data)
    assert called is True
    assert result == "ok"


async def test_services_middleware():
    services = {"service_a": "instance_a", "service_b": 42}
    middleware = ServicesMiddleware(services=services)

    received_data = {}

    async def dummy_handler(event, data):
        nonlocal received_data
        received_data = dict(data)
        return "done"

    initial_data = {"existing": True}
    res = await middleware(dummy_handler, MockUpdate(), initial_data)
    assert res == "done"
    assert received_data["existing"] is True
    assert received_data["service_a"] == "instance_a"
    assert received_data["service_b"] == 42
