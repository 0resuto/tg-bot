"""Controller for retrieving available chats for the dashboard selector."""

from __future__ import annotations

from aiohttp import web
from sqlalchemy import select

from bot.infrastructure.database.tables import ChatORM
from bot.log import get_logger
from bot.web.dependencies import WebContainer
from bot.web.services.simulator_service import SIMULATOR_CHAT_ID

logger = get_logger(__name__)


async def handle_get_chats(request: web.Request) -> web.Response:
    """GET /api/chats - List all available group chats for inspection."""
    container: WebContainer = request.app["container"]
    chats: list[dict[str, object]] = []

    if container.session_factory:
        try:
            async with container.session_factory() as session:
                stmt = select(ChatORM).order_by(ChatORM.added_at.desc())
                result = await session.execute(stmt)
                records = result.scalars().all()
                for rec in records:
                    chats.append(
                        {
                            "chat_id": rec.chat_id,
                            "title": rec.title or f"Chat {rec.chat_id}",
                            "is_active": rec.is_active,
                            "created_at": rec.added_at.isoformat() if rec.added_at else None,
                            "is_simulator": rec.chat_id == SIMULATOR_CHAT_ID,
                        }
                    )
        except Exception as exc:
            logger.error("Failed to query chats from database", error=str(exc))

    # If simulator is enabled and not already in list, prepend dev test chat
    if container.config.enable_simulator and not any(
        c["chat_id"] == SIMULATOR_CHAT_ID for c in chats
    ):
        chats.insert(
            0,
            {
                "chat_id": SIMULATOR_CHAT_ID,
                "title": "🎮 Dev Test Group (Simulator)",
                "is_active": True,
                "created_at": None,
                "is_simulator": True,
            },
        )

    return web.json_response({"chats": chats})
