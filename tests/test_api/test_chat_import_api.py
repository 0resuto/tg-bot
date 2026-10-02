"""Unit tests for Chat History Import REST endpoints."""

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from bot.api.dependencies import WebContainer
from bot.api.server import create_web_app
from bot.api.services.chat_import_service import ChatImportService
from bot.config import Settings, WebConfig


@pytest.fixture
def import_container():
    """Create test WebContainer with mocked services for import testing."""
    web_config = WebConfig(enable_simulator=False)
    settings = Settings()

    container = MagicMock(spec=WebContainer)
    container.is_initialized = True
    container.config = web_config
    container.settings = settings

    # Wire real or mocked ChatImportService
    service = ChatImportService(settings=settings, container=container)
    container.chat_import_service = service
    container.memory_backend = MagicMock()
    container.memory_backend.ingest_episode = AsyncMock()
    container.member_repo = MagicMock()
    container.member_repo.upsert_member = AsyncMock()

    return container


@pytest.mark.asyncio
async def test_import_preview_endpoint(import_container):
    """POST /api/import/preview should return parsing and chunking statistics."""
    app = create_web_app(import_container.config, container=import_container)

    export_payload = {
        "id": 123456,
        "name": "Test Group",
        "type": "public_supergroup",
        "messages": [
            {
                "id": 1,
                "type": "message",
                "from": "Alice",
                "from_id": "user1",
                "text": "Deploying Neo4j",
            },
            {"id": 2, "type": "message", "from": "Bob", "from_id": "user2", "text": "Ok"},  # Noise
            {
                "id": 3,
                "type": "message",
                "from": "Bob",
                "from_id": "user2",
                "text": "Graphiti cluster is up",
            },
        ],
    }

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        res = await client.post(
            "/api/import/preview",
            json={"data": export_payload, "gap_minutes": 20, "max_messages": 10},
        )

    assert res.status_code == 200
    data = res.json()
    assert data["chat_title"] == "Test Group"
    assert data["total_raw_messages"] == 3
    assert data["meaningful_messages"] == 2
    assert data["dropped_noise_messages"] == 1
    assert data["total_episodes"] == 1
    assert len(data["sample_episodes"]) == 1
    assert "Deploying Neo4j" in data["sample_episodes"][0]["text"]


@pytest.mark.asyncio
async def test_import_preview_invalid_payload(import_container):
    """POST /api/import/preview with invalid payload should return 400 error."""
    app = create_web_app(import_container.config, container=import_container)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        res = await client.post(
            "/api/import/preview",
            json={"data": {"messages": "not-a-list"}},
        )

    assert res.status_code == 400
    assert "error" in res.json()


@pytest.mark.asyncio
async def test_import_start_and_status_endpoints(import_container):
    """POST /api/import/start and GET /api/import/status lifecycle."""
    app = create_web_app(import_container.config, container=import_container)

    export_payload = {
        "id": 123456,
        "name": "Test Group",
        "messages": [
            {
                "id": 1,
                "type": "message",
                "from": "Alice",
                "from_id": "user1",
                "text": "Initial setup",
            },
        ],
    }

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Start import
        start_res = await client.post(
            "/api/import/start",
            json={"data": export_payload, "delay": 0.0, "no_db": True},
        )
        assert start_res.status_code == 200
        start_data = start_res.json()
        assert start_data["status"] in ("running", "completed")

        # Query status
        status_res = await client.get("/api/import/status")
        assert status_res.status_code == 200
        status_data = status_res.json()
        assert "status" in status_data
        assert "total_episodes" in status_data

        # Cancel
        cancel_res = await client.post("/api/import/cancel")
        assert cancel_res.status_code == 200
