"""Dependency injection container and lifecycle manager for web dashboard."""

from __future__ import annotations

import inspect
from typing import Any

import redis.asyncio as aioredis
from fastapi import Request
from neo4j import AsyncDriver, AsyncGraphDatabase

from bot.api.services.chat_import_service import ChatImportService
from bot.api.services.graph_service import GraphVisualizerService
from bot.api.services.health_service import SystemHealthService
from bot.api.services.memory_query_service import MemoryQueryService
from bot.api.services.simulator_service import ChatSimulatorService
from bot.config import Settings, WebConfig
from bot.db import (
    GraphitiMemoryBackend,
    MemberRepository,
    create_async_engine_instance,
    create_session_factory,
)
from bot.log import get_logger
from bot.services.admin_notifier import AdminNotifier
from bot.services.context_builder import ContextBuilder
from bot.services.debouncer import MessageDebouncer
from bot.services.llm import OpenAILLMProvider
from bot.services.memory_service import MemoryService
from bot.services.mention_detector import MentionDetector
from bot.services.response_service import ResponseService

logger = get_logger(__name__)


class WebContainer:
    """Encapsulates all database connections, core services, and web presentation services."""

    settings: Settings
    config: WebConfig
    is_initialized: bool = False

    # Database and infrastructure
    engine: Any = None
    session_factory: Any = None
    redis: aioredis.Redis | None = None
    neo4j_driver: AsyncDriver | None = None

    # Repositories
    member_repo: MemberRepository | None = None

    # Core bot services
    memory_backend: GraphitiMemoryBackend | None = None
    llm_provider: OpenAILLMProvider | None = None
    memory_service: MemoryService | None = None
    context_builder: ContextBuilder | None = None
    debouncer: MessageDebouncer | None = None
    mention_detector: MentionDetector | None = None
    response_service: ResponseService | None = None

    # Web presentation services
    health_service: SystemHealthService
    graph_service: GraphVisualizerService
    memory_query_service: MemoryQueryService | None = None
    simulator_service: ChatSimulatorService | None = None
    chat_import_service: ChatImportService
    admin_notifier: AdminNotifier | None = None
    bot: Any | None = None

    def __init__(self, settings: Settings | None = None, config: WebConfig | None = None) -> None:
        self.settings = settings or Settings()
        self.config = config or WebConfig()
        self.is_initialized = False

        # Database and infrastructure
        self.engine = None
        self.session_factory = None
        self.redis = None
        self.neo4j_driver = None

        # Repositories
        self.member_repo = None

        # Core bot services
        self.memory_backend = None
        self.llm_provider = None
        self.memory_service = None
        self.context_builder = None
        self.debouncer = None
        self.mention_detector = None
        self.response_service = None

        # Web presentation services
        self.health_service = SystemHealthService(self.settings)
        self.graph_service = GraphVisualizerService(self.settings)
        self.memory_query_service = None
        self.simulator_service = None
        self.chat_import_service = ChatImportService(self.settings, self)
        self.admin_notifier = None
        self.bot = None

    async def init(self) -> None:
        """Initialize database connections and assemble service graph."""
        logger.info("Initializing WebContainer services...")
        await self.health_service.check_all()

        # PostgreSQL
        if any(
            item["id"] == "postgres" and item["status"] == "ok"
            for item in self.health_service.items
        ):
            try:
                self.engine = create_async_engine_instance(self.settings.postgres_dsn)
                self.session_factory = create_session_factory(self.engine)
                self.member_repo = MemberRepository(self.session_factory)
            except Exception as exc:
                logger.error("Failed to initialize PostgreSQL in WebContainer", error=str(exc))

        # Redis
        if any(
            item["id"] == "redis" and item["status"] == "ok" for item in self.health_service.items
        ):
            try:
                self.redis = aioredis.from_url(self.settings.redis_url)
                self.context_builder = ContextBuilder(
                    redis_client=self.redis,
                    window_minutes=int(self.settings.context_window_minutes),
                    min_messages=int(self.settings.context_min_messages),
                    ttl_seconds=int(self.settings.context_ttl_seconds),
                )
            except Exception as exc:
                logger.error("Failed to initialize Redis in WebContainer", error=str(exc))

        # OpenAI LLM
        if self.settings.openai_api_key:
            self.llm_provider = OpenAILLMProvider(
                api_key=self.settings.openai_api_key,
                default_model=self.settings.openai_response_model,
                timeout=self.settings.openai_timeout_seconds,
            )

        # Neo4j Driver (shared for web queries & visualization)
        if (
            any(
                item["id"] == "neo4j" and item["status"] == "ok"
                for item in self.health_service.items
            )
            and self.settings.neo4j_password
        ):
            try:
                self.neo4j_driver = AsyncGraphDatabase.driver(
                    self.settings.neo4j_uri,
                    auth=(self.settings.neo4j_user, self.settings.neo4j_password),
                )
            except Exception as exc:
                logger.error("Failed to initialize Neo4j driver in WebContainer", error=str(exc))

        self.graph_service = GraphVisualizerService(self.settings, driver=self.neo4j_driver)

        # Graphiti / Neo4j
        if (
            any(
                item["id"] == "neo4j" and item["status"] == "ok"
                for item in self.health_service.items
            )
            and self.settings.openai_api_key
        ):
            try:
                self.memory_backend = GraphitiMemoryBackend(
                    neo4j_uri=self.settings.neo4j_uri,
                    neo4j_user=self.settings.neo4j_user,
                    neo4j_password=self.settings.neo4j_password,
                    openai_api_key=self.settings.openai_api_key,
                    extraction_model=self.settings.openai_extraction_model,
                    embedding_model=self.settings.openai_embedding_model,
                )
            except Exception as exc:
                logger.error("Failed to initialize Graphiti in WebContainer", error=str(exc))
        # Memory Service
        if self.memory_backend and self.redis:
            self.memory_service = MemoryService(
                memory=self.memory_backend,
                search_limit_quick=self.settings.memory_search_limit_quick,
                search_limit_deep=self.settings.memory_search_limit_deep,
            )

        self.memory_query_service = MemoryQueryService(
            settings=self.settings,
            memory_service=self.memory_service,
            driver=self.neo4j_driver,
        )

        # Response Service
        bot_names = self.settings.bot_name_list or ["Bot"]
        self.mention_detector = MentionDetector(
            bot_names=bot_names,
            bot_user_id=self.settings.admin_user_id or 999999999,
            bot_username=f"{bot_names[0].lower()}_bot",
        )

        # Admin Notifier
        token = (self.settings.telegram_bot_token or "").strip()
        if token and not token.startswith("YOUR_"):
            try:
                from aiogram import Bot

                self.bot = Bot(token=token)
            except Exception as exc:
                logger.warning(
                    "Could not initialize Bot for AdminNotifier in WebContainer", error=str(exc)
                )

        self.admin_notifier = AdminNotifier(
            admin_chat_id=self.settings.admin_chat_id or self.settings.admin_user_id,
            bot=self.bot,
        )

        if self.llm_provider and self.memory_service and self.context_builder:
            self.response_service = ResponseService(
                llm=self.llm_provider,
                memory_service=self.memory_service,
                context_builder=self.context_builder,
                persona_prompt=self.settings.get_persona_prompt(),
                response_model=self.settings.openai_response_model,
                admin_notifier=self.admin_notifier,
                group_chat_id=self.settings.group_chat_id,
                max_response_tokens=self.settings.openai_response_max_tokens,
            )

        # Simulator Service (if enabled)
        if self.config.enable_simulator:
            if self.redis and self.memory_service:
                memory_service = self.memory_service

                async def on_debounce_flush(c_id: int, u_id: int, msgs: list[Any]) -> None:
                    if msgs:
                        await memory_service.ingest_messages(c_id, u_id, msgs)

                self.debouncer = MessageDebouncer(
                    debounce_seconds=float(self.settings.debounce_seconds),
                    on_flush=on_debounce_flush,
                )

            self.simulator_service = ChatSimulatorService(
                settings=self.settings,
                member_repo=self.member_repo,
                context_builder=self.context_builder,
                debouncer=self.debouncer,
                mention_detector=self.mention_detector,
                response_service=self.response_service,
                admin_notifier=self.admin_notifier,
            )

        self.is_initialized = True

    async def dispose(self) -> None:
        """Close open connection pools gracefully."""
        self.is_initialized = False
        if self.debouncer:
            try:
                await self.debouncer.shutdown()
            except Exception as exc:
                logger.warning("Error shutting down debouncer in WebContainer", error=str(exc))
        if self.memory_backend:
            try:
                await self.memory_backend.close()
            except Exception as exc:
                logger.warning("Error closing memory_backend in WebContainer", error=str(exc))
        if self.llm_provider and hasattr(self.llm_provider, "close"):
            try:
                await self.llm_provider.close()
            except Exception as exc:
                logger.warning("Error closing llm_provider in WebContainer", error=str(exc))
        if self.engine:
            try:
                await self.engine.dispose()
            except Exception as exc:
                logger.warning("Error disposing engine in WebContainer", error=str(exc))
        if self.redis:
            try:
                await self.redis.aclose()
            except Exception as exc:
                logger.warning("Error closing redis in WebContainer", error=str(exc))
        if self.neo4j_driver:
            try:
                if hasattr(self.neo4j_driver, "close"):
                    res = self.neo4j_driver.close()
                    if inspect.isawaitable(res):
                        await res
            except Exception as exc:
                logger.warning("Error closing neo4j_driver in WebContainer", error=str(exc))
        if self.bot and self.bot.session:
            try:
                await self.bot.session.close()
            except Exception as exc:
                logger.warning("Error closing bot session in WebContainer", error=str(exc))


def get_container(request: Request) -> WebContainer:
    """FastAPI dependency to retrieve the WebContainer from app state."""
    container: WebContainer = request.app.state.container
    return container
