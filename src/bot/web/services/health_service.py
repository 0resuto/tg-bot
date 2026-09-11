"""Service for checking infrastructure health and production diagnostics."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import redis.asyncio as aioredis
from neo4j import GraphDatabase

from bot.config import Settings
from bot.infrastructure.database.engine import create_async_engine_instance
from bot.log import get_logger

logger = get_logger(__name__)


class SystemHealthService:
    """Diagnostic service verifying database, redis, neo4j, and LLM readiness."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.items: list[dict[str, Any]] = []
        self.all_ready: bool = False

    async def check_all(self) -> dict[str, Any]:
        """Execute connectivity and health checks against all production services."""
        checks: list[dict[str, Any]] = []

        # 1. OpenAI LLM Check
        ai_check: dict[str, Any] = {
            "id": "openai",
            "name": "OpenAI LLM",
            "target": self.settings.openai_response_model,
            "status": "ok",
            "message": f"Model: {self.settings.openai_response_model}",
            "error": None,
        }
        if not self.settings.openai_api_key or not self.settings.openai_api_key.strip():
            ai_check["status"] = "error"
            ai_check["error"] = "OPENAI_API_KEY is not set in .env"
            ai_check["message"] = "Missing API key"
        else:
            ai_check["status"] = "ok"
            ai_check["message"] = f"Key configured, model: {self.settings.openai_response_model}"
        checks.append(ai_check)

        # 2. PostgreSQL Check
        pg_check: dict[str, Any] = {
            "id": "postgres",
            "name": "PostgreSQL Database",
            "target": f"{self.settings.postgres_host}:{self.settings.postgres_port}/{self.settings.postgres_db}",
            "status": "ok",
            "message": "Connected",
            "error": None,
        }
        try:
            from sqlalchemy import text

            engine = create_async_engine_instance(self.settings.postgres_dsn)
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            await engine.dispose()
            pg_check["status"] = "ok"
            pg_check["message"] = "Connected"
        except Exception as exc:
            logger.warning("PostgreSQL health check failed", error=str(exc))
            pg_check["status"] = "error"
            pg_check["error"] = f"PostgreSQL error: {exc}"
            pg_check["message"] = (
                f"Cannot connect to {self.settings.postgres_host}:{self.settings.postgres_port}"
            )
        checks.append(pg_check)

        # 3. Redis Check
        redis_check: dict[str, Any] = {
            "id": "redis",
            "name": "Redis Context & Debounce",
            "target": self.settings.redis_url,
            "status": "ok",
            "message": "PONG received",
            "error": None,
        }
        try:
            r = aioredis.from_url(self.settings.redis_url)
            await r.ping()
            await r.aclose()
            redis_check["status"] = "ok"
            redis_check["message"] = "PONG received"
        except Exception as exc:
            logger.warning("Redis health check failed", error=str(exc))
            redis_check["status"] = "error"
            redis_check["error"] = f"Redis error: {exc}"
            redis_check["message"] = f"Cannot connect to {self.settings.redis_url}"
        checks.append(redis_check)

        # 4. Neo4j & Graphiti Memory Check
        neo_check: dict[str, Any] = {
            "id": "neo4j",
            "name": "Neo4j / Graphiti Memory",
            "target": self.settings.neo4j_uri,
            "status": "ok",
            "message": "Knowledge graph connected",
            "error": None,
        }
        if not self.settings.neo4j_password:
            neo_check["status"] = "error"
            neo_check["error"] = "NEO4J_PASSWORD is empty in .env"
            neo_check["message"] = "Missing password"
        else:
            try:
                driver = GraphDatabase.driver(
                    self.settings.neo4j_uri,
                    auth=(self.settings.neo4j_user, self.settings.neo4j_password),
                )
                driver.verify_connectivity()
                driver.close()
                neo_check["status"] = "ok"
                neo_check["message"] = f"Bolt connected ({self.settings.neo4j_user})"
            except Exception as exc:
                logger.warning("Neo4j health check failed", error=str(exc))
                neo_check["status"] = "error"
                neo_check["error"] = f"Neo4j error: {exc}"
                neo_check["message"] = f"Cannot connect to {self.settings.neo4j_uri}"
        checks.append(neo_check)

        self.items = checks
        self.all_ready = all(item["status"] == "ok" for item in checks)
        return {
            "all_ready": self.all_ready,
            "items": self.items,
            "checked_at": datetime.now(UTC).isoformat(),
        }
