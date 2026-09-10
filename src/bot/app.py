"""
Main application factory and lifecycle management.
"""

from __future__ import annotations

import asyncio
import logging
from typing import cast

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties

from bot.config import Settings
from bot.domain.models import ChatMessage
from bot.infrastructure.database.engine import create_async_engine, create_session_factory
from bot.infrastructure.llm.openai_provider import OpenAILLMProvider
from bot.infrastructure.memory.graphiti_backend import GraphitiMemoryBackend
from bot.infrastructure.redis.client import create_redis_client
from bot.interfaces.task_runner import AsyncioTaskRunner
from bot.log import setup_logging
from bot.repositories import ChatRepository, MemberRepository, TokenUsageRepository
from bot.services.context_builder import ContextBuilder
from bot.services.debouncer import MessageDebouncer
from bot.services.memory_service import MemoryService
from bot.services.mention_detector import MentionDetector
from bot.services.response_service import ResponseService
from bot.services.sensitive_filter import SensitiveFilter
from bot.telegram.dispatcher import create_dispatcher

logger = logging.getLogger(__name__)


def run_migrations(settings: Settings) -> None:
    """Run alembic migrations synchronously in a thread."""
    import alembic.command
    import alembic.config

    alembic_cfg = alembic.config.Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", settings.postgres_dsn_sync)
    alembic.command.upgrade(alembic_cfg, "head")
    logger.info("Alembic migrations completed successfully.")


async def main() -> None:
    """
    Main application entry point. Wires up all dependencies and runs the bot.
    """
    # 1. Load settings
    settings = Settings()

    # 2. Setup logging
    setup_logging()
    logger.info("Starting Telegram Memory Bot...")

    # 3. Create infrastructure
    # Run migrations in an executor
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, run_migrations, settings)

    engine = create_async_engine(settings.postgres_dsn)
    session_factory = create_session_factory(engine)

    redis_client = create_redis_client(settings.redis_url)

    graphiti_backend = GraphitiMemoryBackend(
        neo4j_uri=settings.neo4j_uri,
        neo4j_user=settings.neo4j_user,
        neo4j_password=settings.neo4j_password,
        openai_api_key=settings.openai_api_key,
        extraction_model=settings.openai_extraction_model,
        embedding_model=settings.openai_embedding_model,
    )

    llm_provider = OpenAILLMProvider(
        api_key=settings.openai_api_key,
        default_model=settings.openai_response_model,
        default_chat_id=settings.admin_chat_id or 0,
    )

    task_runner = AsyncioTaskRunner()

    # 4. Create repositories
    chat_repo = ChatRepository(session_factory)
    member_repo = MemberRepository(session_factory)
    token_repo = TokenUsageRepository(session_factory)

    # 5. Create services
    sensitive_filter = SensitiveFilter(
        enabled=settings.sensitive_filter_enabled, categories=settings.sensitive_category_list
    )

    memory_service = MemoryService(
        memory=graphiti_backend,
        sensitive_filter=sensitive_filter,
        token_repo=token_repo,
        redis_client=redis_client,
        cache_ttl=settings.memory_user_summary_cache_ttl,
        search_limit_quick=settings.memory_search_limit_quick,
        search_limit_deep=settings.memory_search_limit_deep,
    )

    context_builder = ContextBuilder(
        redis=redis_client,
        window_minutes=settings.context_window_minutes,
        min_messages=settings.context_min_messages,
    )

    response_service = ResponseService(
        llm=llm_provider,
        memory_service=memory_service,
        context_builder=context_builder,
        token_repo=token_repo,
        persona_prompt=settings.get_persona_prompt(),
        response_model=settings.openai_response_model,
        bot_language=settings.bot_language,
    )

    # Note: MentionDetector needs bot info, which we will fetch in the startup hook.
    # We will initialize it as None first and set it during startup.
    mention_detector: MentionDetector | None = None

    async def on_flush_debouncer(chat_id: int, user_id: int, messages: list[ChatMessage]) -> None:
        """Callback for debouncer when messages are flushed."""
        logger.info("Flushing %d messages for chat %s user %s", len(messages), chat_id, user_id)
        task_runner.schedule(
            memory_service.ingest_messages(chat_id, user_id, messages),
            name=f"ingest_{chat_id}_{user_id}",
        )

    debouncer = MessageDebouncer(
        redis_client=redis_client,
        debounce_seconds=settings.debounce_seconds,
        on_flush=on_flush_debouncer,
    )

    # Pack services for dispatcher
    services = {
        "memory_service": memory_service,
        "response_service": response_service,
        "context_builder": context_builder,
        "debouncer": debouncer,
        "chat_repo": chat_repo,
        "member_repo": member_repo,
        "token_repo": token_repo,
        "task_runner": task_runner,
        "settings": settings,
    }

    # 6. Create bot and dispatcher
    bot = Bot(token=settings.telegram_bot_token, default=DefaultBotProperties(parse_mode="HTML"))
    dp = create_dispatcher(settings, services, redis_client)

    # 7. Register startup/shutdown hooks
    @dp.startup()
    async def on_startup(bot: Bot) -> None:
        logger.info("Running startup hooks...")
        await graphiti_backend.init()

        bot_user = await bot.get_me()
        logger.info("Bot info fetched: @%s (ID: %d)", bot_user.username, bot_user.id)

        nonlocal mention_detector
        mention_detector = MentionDetector(
            bot_names=settings.bot_name_list,
            bot_user_id=bot_user.id,
            bot_username=cast(str, bot_user.username),
        )
        services["mention_detector"] = mention_detector
        # Load active chat IDs for allowlist
        active_chats = await chat_repo.get_active_chat_ids()
        allowed = set(active_chats)
        if settings.admin_chat_id:
            allowed.add(settings.admin_chat_id)
        if "allowlist" in dp:
            dp["allowlist"].update_allowed_chats(allowed)
        logger.info("Startup complete, allowed chats: %s", allowed)

    @dp.shutdown()
    async def on_shutdown(bot: Bot) -> None:
        logger.info("Running shutdown hooks...")
        await debouncer.shutdown()
        await task_runner.shutdown()
        await graphiti_backend.close()
        await redis_client.aclose()
        await engine.dispose()
        await bot.session.close()
        logger.info("Shutdown complete.")

    # 8. Start polling
    try:
        await dp.start_polling(bot, allowed_updates=["message", "edited_message", "callback_query"])
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped by user.")
    except Exception:
        logger.exception("Fatal error during polling.")
