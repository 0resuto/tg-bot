from __future__ import annotations

from bot.telegram.middlewares.services import ServicesMiddleware


class MockUpdate:
    pass


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
