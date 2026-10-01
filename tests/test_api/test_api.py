"""Unit tests for the FastAPI web server and REST API controllers."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from bot.api.dependencies import WebContainer
from bot.api.server import create_web_app
from bot.api.services.simulator_service import SIMULATOR_CHAT_ID
from bot.config import Settings, WebConfig
from bot.models import ChatMessage


@pytest.mark.asyncio
async def test_web_config_defaults():
    config = WebConfig()
    assert config.host == "127.0.0.1"
    assert config.port == 8080
    assert config.enable_simulator is False
    assert config.static_dir.name == "dist"


@pytest.fixture
def dashboard_container():
    web_config = WebConfig(enable_simulator=False)
    settings = Settings()

    container = MagicMock(spec=WebContainer)
    container.is_initialized = True
    container.config = web_config
    container.settings = settings

    # Mock health service
    health_service = MagicMock()
    health_service.all_ready = True
    health_service.items = [
        {"id": "db", "name": "Database", "status": "ok", "error": None},
        {"id": "redis", "name": "Redis", "status": "ok", "error": None},
    ]
    health_service.check_all = AsyncMock(
        return_value={
            "all_ready": True,
            "items": health_service.items,
            "checked_at": "2026-09-11T12:00:00Z",
        }
    )
    container.health_service = health_service

    # Mock graph service
    graph_service = MagicMock()
    graph_service.get_graph = AsyncMock(
        return_value={
            "nodes": [{"id": 1, "label": "User", "group": "User"}],
            "edges": [],
        }
    )
    container.graph_service = graph_service

    # Mock memory query service
    memory_query_service = MagicMock()
    memory_query_service.get_memories = AsyncMock(return_value=[])
    memory_query_service.get_stats = AsyncMock(
        return_value={"facts_count": 10, "entities_count": 5}
    )
    container.memory_query_service = memory_query_service

    # Mock context builder
    context_builder = MagicMock()
    context_builder.get_context = AsyncMock(return_value=[])
    container.context_builder = context_builder

    # Simulator service is None when disabled
    container.simulator_service = None
    container.session_factory = None
    container.admin_notifier = None

    return container


@pytest.fixture
async def dashboard_client(dashboard_container):
    app = create_web_app(container=dashboard_container, config=dashboard_container.config)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client


@pytest.mark.asyncio
async def test_health_status(dashboard_client):
    resp = await dashboard_client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["all_ready"] is True
    assert "items" in data
    assert len(data["items"]) == 2


@pytest.mark.asyncio
async def test_chats_list_production(dashboard_client):
    resp = await dashboard_client.get("/api/chats")
    assert resp.status_code == 200
    data = resp.json()
    assert "chats" in data
    assert isinstance(data["chats"], list)
    assert len(data["chats"]) == 0


@pytest.mark.asyncio
async def test_simulator_endpoints_forbidden_when_disabled(dashboard_client):
    resp = await dashboard_client.get("/api/simulator/presets")
    assert resp.status_code == 200
    data = resp.json()
    assert data["presets"] == []

    resp_send = await dashboard_client.post(
        "/api/simulator/send_message",
        json={"user_id": 1, "text": "hello"},
    )
    assert resp_send.status_code == 403


@pytest.mark.asyncio
async def test_stats_endpoint(dashboard_client):
    resp = await dashboard_client.get("/api/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "all_ready" in data
    assert data["all_ready"] is True
    assert "llm_model" in data


@pytest.mark.asyncio
async def test_logs_endpoint(dashboard_client):
    resp = await dashboard_client.get("/api/logs")
    assert resp.status_code == 200
    data = resp.json()
    assert "logs" in data
    assert isinstance(data["logs"], list)


@pytest.mark.asyncio
async def test_get_graph_endpoint(dashboard_client, dashboard_container):
    resp = await dashboard_client.get("/api/graph?chat_id=123")
    assert resp.status_code == 200
    data = resp.json()
    assert "nodes" in data
    assert "edges" in data
    dashboard_container.graph_service.get_graph.assert_awaited_once_with(123)


@pytest.mark.asyncio
async def test_get_graph_requires_chat_id(dashboard_client):
    resp = await dashboard_client.get("/api/graph")
    assert resp.status_code == 400
    assert resp.json()["error"] == "chat_id query parameter is required"


@pytest.mark.asyncio
async def test_get_memories_endpoint(dashboard_client, dashboard_container):
    resp = await dashboard_client.get("/api/memories?chat_id=123")
    assert resp.status_code == 200
    data = resp.json()
    assert "facts" in data
    dashboard_container.memory_query_service.get_memories.assert_awaited_once_with(123)


@pytest.mark.asyncio
async def test_get_memories_requires_chat_id(dashboard_client):
    resp = await dashboard_client.get("/api/memories")
    assert resp.status_code == 400
    assert resp.json()["error"] == "chat_id query parameter is required"


@pytest.mark.asyncio
async def test_checklist_endpoint_removed(dashboard_client):
    resp = await dashboard_client.get("/api/checklist")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_context_endpoint_success(dashboard_client, dashboard_container):
    msg = ChatMessage(
        chat_id=123,
        user_id=456,
        text="Hello bot",
        display_name="Alice",
        timestamp=datetime(2026, 9, 17, 12, 0, tzinfo=UTC),
        message_id=42,
    )
    dashboard_container.context_builder.get_context = AsyncMock(return_value=[msg])

    resp = await dashboard_client.get("/api/context?chat_id=123")
    assert resp.status_code == 200
    data = resp.json()
    assert "messages" in data
    assert len(data["messages"]) == 1
    assert data["messages"][0]["text"] == "Hello bot"
    assert data["messages"][0]["display_name"] == "Alice"
    dashboard_container.context_builder.get_context.assert_awaited_once_with(123)


@pytest.mark.asyncio
async def test_get_context_service_unavailable(dashboard_client, dashboard_container):
    dashboard_container.context_builder = None
    resp = await dashboard_client.get("/api/context?chat_id=123")
    assert resp.status_code == 503
    data = resp.json()
    assert "error" in data


@pytest.mark.asyncio
async def test_get_context_internal_server_error(dashboard_client, dashboard_container):
    dashboard_container.context_builder.get_context = AsyncMock(
        side_effect=RuntimeError("Redis connection failure")
    )
    resp = await dashboard_client.get("/api/context?chat_id=123")
    assert resp.status_code == 500
    data = resp.json()
    assert "error" in data


@pytest.fixture
def simulator_container():
    web_config = WebConfig(enable_simulator=True)
    settings = Settings()

    container = MagicMock(spec=WebContainer)
    container.is_initialized = True
    container.config = web_config
    container.settings = settings

    simulator_service = MagicMock()
    simulator_service.get_presets = MagicMock(
        return_value=[{"name": "Mock Preset", "description": "Test", "script": []}]
    )
    simulator_service.send_simulated_message = AsyncMock(
        return_value={"success": True, "bot_response": "Hello simulated"}
    )
    container.simulator_service = simulator_service

    container.session_factory = None
    container.health_service = MagicMock()
    container.health_service.all_ready = True
    container.health_service.items = []
    container.memory_query_service = None
    container.admin_notifier = None

    return container


@pytest.fixture
async def simulator_client(simulator_container):
    app = create_web_app(container=simulator_container, config=simulator_container.config)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client


@pytest.mark.asyncio
async def test_simulator_presets_allowed(simulator_client):
    resp = await simulator_client.get("/api/simulator/presets")
    assert resp.status_code == 200
    data = resp.json()
    assert "presets" in data
    assert len(data["presets"]) == 1
    assert data["presets"][0]["name"] == "Mock Preset"


@pytest.mark.asyncio
async def test_simulator_send_message_allowed(simulator_client):
    resp = await simulator_client.post(
        "/api/simulator/send_message",
        json={"user_id": 1, "user_name": "Alice", "text": "Hello bot"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["bot_response"] == "Hello simulated"


@pytest.mark.asyncio
async def test_chats_list_prepends_sandbox_when_enabled(simulator_client):
    resp = await simulator_client.get("/api/chats")
    assert resp.status_code == 200
    data = resp.json()
    assert "chats" in data
    chats = data["chats"]
    assert len(chats) >= 1
    assert chats[0]["chat_id"] == SIMULATOR_CHAT_ID
    assert "Simulator" in chats[0]["title"]
