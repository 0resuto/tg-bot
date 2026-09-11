"""Unit tests for the modular web server and REST API controllers."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from aiohttp.test_utils import AioHTTPTestCase

from bot.config import Settings
from bot.web.config import WebConfig
from bot.web.dependencies import WebContainer
from bot.web.server import create_web_app
from bot.web.services.simulator_service import SIMULATOR_CHAT_ID


@pytest.mark.asyncio
async def test_web_config_defaults():
    config = WebConfig()
    assert config.host == "127.0.0.1"
    assert config.port == 8080
    assert config.enable_simulator is False
    assert config.static_dir.name == "dist"


class TestDashboardServer(AioHTTPTestCase):
    async def get_application(self):
        self.web_config = WebConfig(enable_simulator=False)
        self.settings = Settings()

        self.container = MagicMock(spec=WebContainer)
        self.container.is_initialized = True
        self.container.config = self.web_config
        self.container.settings = self.settings

        # Mock health service
        self.health_service = MagicMock()
        self.health_service.all_ready = True
        self.health_service.items = [
            {"id": "db", "name": "Database", "status": "ok", "error": None},
            {"id": "redis", "name": "Redis", "status": "ok", "error": None},
        ]
        self.health_service.check_all = AsyncMock(
            return_value={
                "all_ready": True,
                "items": self.health_service.items,
                "checked_at": "2026-09-11T12:00:00Z",
            }
        )
        self.container.health_service = self.health_service

        # Mock graph service
        self.graph_service = MagicMock()
        self.graph_service.get_chat_graph = AsyncMock(
            return_value={
                "nodes": [{"id": 1, "label": "User", "group": "User"}],
                "edges": [],
            }
        )
        self.container.graph_service = self.graph_service

        # Mock memory query service
        self.memory_query_service = MagicMock()
        self.memory_query_service.get_memories_for_chat = AsyncMock(return_value=[])
        self.memory_query_service.forget_fact = AsyncMock(return_value=True)
        self.memory_query_service.get_stats = AsyncMock(
            return_value={"facts_count": 10, "entities_count": 5}
        )
        self.container.memory_query_service = self.memory_query_service

        # Simulator service is None when disabled
        self.container.simulator_service = None

        # Session factory is None or returns mocked records
        self.container.session_factory = None

        return create_web_app(container=self.container, config=self.web_config)

    async def test_health_checklist(self):
        resp = await self.client.request("GET", "/api/checklist")
        assert resp.status == 200
        data = await resp.json()
        assert "items" in data
        assert len(data["items"]) == 2

    async def test_chats_list_production(self):
        resp = await self.client.request("GET", "/api/chats")
        assert resp.status == 200
        data = await resp.json()
        assert "chats" in data
        assert isinstance(data["chats"], list)
        assert len(data["chats"]) == 0

    async def test_simulator_endpoints_forbidden_when_disabled(self):
        resp = await self.client.request("GET", "/api/simulator/presets")
        assert resp.status == 200
        data = await resp.json()
        # Returns empty users/presets when disabled
        assert data["presets"] == []

        resp_send = await self.client.request(
            "POST",
            "/api/simulator/send_message",
            json={"user_id": 1, "text": "hello"},
        )
        assert resp_send.status == 403

    async def test_stats_endpoint(self):
        resp = await self.client.request("GET", "/api/stats")
        assert resp.status == 200
        data = await resp.json()
        assert "all_ready" in data
        assert data["all_ready"] is True
        assert "llm_model" in data

    async def test_logs_endpoint(self):
        resp = await self.client.request("GET", "/api/logs")
        assert resp.status == 200
        data = await resp.json()
        assert "logs" in data
        assert isinstance(data["logs"], list)


class TestSimulatorEnabledServer(AioHTTPTestCase):
    async def get_application(self):
        self.web_config = WebConfig(enable_simulator=True)
        self.settings = Settings()

        self.container = MagicMock(spec=WebContainer)
        self.container.is_initialized = True
        self.container.config = self.web_config
        self.container.settings = self.settings

        self.simulator_service = MagicMock()
        self.simulator_service.get_presets = MagicMock(
            return_value=[{"name": "Mock Preset", "description": "Test", "script": []}]
        )
        self.simulator_service.send_simulated_message = AsyncMock(
            return_value={"success": True, "bot_response": "Hello simulated"}
        )
        self.container.simulator_service = self.simulator_service

        self.container.session_factory = None
        self.container.health_service = MagicMock()
        self.container.health_service.all_ready = True
        self.container.health_service.items = []
        self.container.memory_query_service = None

        return create_web_app(container=self.container, config=self.web_config)

    async def test_simulator_presets_allowed(self):
        resp = await self.client.request("GET", "/api/simulator/presets")
        assert resp.status == 200
        data = await resp.json()
        assert "presets" in data
        assert len(data["presets"]) == 1
        assert data["presets"][0]["name"] == "Mock Preset"

    async def test_simulator_send_message_allowed(self):
        resp = await self.client.request(
            "POST",
            "/api/simulator/send_message",
            json={"user_id": 1, "user_name": "Alice", "text": "Hello bot"},
        )
        assert resp.status == 200
        data = await resp.json()
        assert data["success"] is True
        assert data["bot_response"] == "Hello simulated"

    async def test_chats_list_prepends_sandbox_when_enabled(self):
        resp = await self.client.request("GET", "/api/chats")
        assert resp.status == 200
        data = await resp.json()
        assert "chats" in data
        chats = data["chats"]
        assert len(chats) >= 1
        assert chats[0]["chat_id"] == SIMULATOR_CHAT_ID
        assert "Simulator" in chats[0]["title"]
