"""
Main application factory and lifecycle management.
"""

from __future__ import annotations

import sys
from typing import cast

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession

from bot.config import Settings
from bot.db import (
    GraphitiMemoryBackend,
    MemberRepository,
    create_async_engine_instance,
    create_redis_client,
    create_session_factory,
)
from bot.log import get_logger, setup_logging
from bot.models import ChatMessage
from bot.services.admin_notifier import AdminNotifier
from bot.services.context_builder import ContextBuilder
from bot.services.debouncer import MessageDebouncer
from bot.services.llm import OpenAILLMProvider
from bot.services.memory_service import MemoryService
from bot.services.mention_detector import MentionDetector
from bot.services.response_service import ResponseService
from bot.telegram.dispatcher import create_dispatcher

logger = get_logger(__name__)


def build_bot_session(proxy_url: str) -> AiohttpSession | None:
    """Build an aiogram HTTP session, optionally routed through a proxy.

    aiogram ignores the standard ``HTTP_PROXY``/``HTTPS_PROXY`` environment
    variables, so the proxy must be passed explicitly. Returns ``None`` for a
    direct connection.
    """
    proxy = proxy_url.strip()
    if not proxy:
        return None
    logger.info("Telegram API calls will use proxy")
    return AiohttpSession(proxy=proxy)


async def main() -> None:
    """
    Main application entry point. Wires up all dependencies and runs the bot.
    """
    # 1. Load settings
    settings = Settings()

    # 2. Setup logging
    setup_logging(debug=settings.debug)

    # 3. Fail-Fast configuration validation
    try:
        settings.validate_for_bot_runtime()
    except ValueError as err:
        logger.critical(str(err))
        sys.exit(1)

    logger.info("Starting Telegram Memory Bot...")

    # 3. Initialize database layer and services
    engine = create_async_engine_instance(settings.postgres_dsn)
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
        timeout=settings.openai_timeout_seconds,
    )

    # 4. Create repositories
    member_repo = MemberRepository(session_factory)

    # 5. Create services
    memory_service = MemoryService(
        memory=graphiti_backend,
        search_limit_quick=settings.memory_search_limit_quick,
        search_limit_deep=settings.memory_search_limit_deep,
    )

    context_builder = ContextBuilder(
        redis_client=redis_client,
        window_minutes=settings.context_window_minutes,
        min_messages=settings.context_min_messages,
        ttl_seconds=settings.context_ttl_seconds,
    )

    admin_notifier = AdminNotifier(admin_chat_id=settings.admin_chat_id or settings.admin_user_id)

    response_service = ResponseService(
        llm=llm_provider,
        memory_service=memory_service,
        context_builder=context_builder,
        persona_prompt=settings.get_persona_prompt(),
        response_model=settings.openai_response_model,
        admin_notifier=admin_notifier,
        group_chat_id=settings.group_chat_id,
    )

    mention_detector: MentionDetector | None = None

    async def on_flush_debouncer(chat_id: int, user_id: int, messages: list[ChatMessage]) -> None:
        """Callback for debouncer when messages are flushed."""
        logger.info("Flushing messages", count=len(messages), chat_id=chat_id, user_id=user_id)
        await memory_service.ingest_messages(chat_id, user_id, messages)

    debouncer = MessageDebouncer(
        debounce_seconds=settings.debounce_seconds,
        on_flush=on_flush_debouncer,
    )

    services = {
        "memory_service": memory_service,
        "response_service": response_service,
        "context_builder": context_builder,
        "debouncer": debouncer,
        "member_repo": member_repo,
        "admin_notifier": admin_notifier,
        "settings": settings,
    }

    # 6. Create bot and dispatcher
    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode="HTML"),
        session=build_bot_session(settings.telegram_proxy_url),
    )
    admin_notifier.set_bot(bot)
    dp = create_dispatcher(settings, services, redis_client)

    # 7. Register startup/shutdown hooks
    @dp.startup()
    async def on_startup(bot: Bot) -> None:
        logger.info("Running startup hooks...")

        bot_user = await bot.get_me()
        logger.info("Bot info fetched", username=bot_user.username, user_id=bot_user.id)

        nonlocal mention_detector
        mention_detector = MentionDetector(
            bot_names=settings.bot_name_list,
            bot_user_id=bot_user.id,
            bot_username=cast(str, bot_user.username),
        )
        services["mention_detector"] = mention_detector
        if not settings.group_chat_id:
            logger.warning(
                "GROUP_CHAT_ID is not configured or 0; group messages will not be processed"
            )
        if not settings.admin_user_id and not settings.admin_chat_id:
            logger.warning(
                "ADMIN_USER_ID / ADMIN_CHAT_ID is not configured; admin private messages will not be processed"
            )
        logger.info(
            "Startup complete",
            group_chat_id=settings.group_chat_id,
            admin_user_id=settings.admin_user_id,
            admin_chat_id=settings.admin_chat_id,
        )

    @dp.shutdown()
    async def on_shutdown(bot: Bot) -> None:
        logger.info("Running shutdown hooks...")
        for name, cleanup_coro in [
            ("debouncer", debouncer.shutdown()),
            ("graphiti_backend", graphiti_backend.close()),
            ("llm_provider", llm_provider.close()),
            ("redis_client", redis_client.aclose()),
            ("engine", engine.dispose()),
            ("bot_session", bot.session.close()),
        ]:
            try:
                await cleanup_coro
            except Exception as exc:
                logger.warning("Error during shutdown of %s: %s", name, exc)
        logger.info("Shutdown complete.")

    # 8. Start polling
    try:
        await dp.start_polling(bot, allowed_updates=["message"])
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped by user.")
    except Exception:
        logger.exception("Fatal error during polling.")
