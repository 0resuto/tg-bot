"""Consolidated FastAPI router for the web dashboard and chat simulator."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select

from bot.api.dependencies import WebContainer, get_container
from bot.api.services.simulator_service import PRESET_USERS, SIMULATOR_CHAT_ID
from bot.db.tables import ChatORM
from bot.log import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api")


# --------------------------------------------------------------------------
# Request Schemas
# --------------------------------------------------------------------------


class SimulateMessageRequest(BaseModel):
    """Payload for simulating a user message in the interactive sandbox."""

    user_id: int = 1
    user_name: str = "Alice"
    text: str = ""
    reply_to_bot: bool = False


# --------------------------------------------------------------------------
# Health & Diagnostics
# --------------------------------------------------------------------------


@router.get("/health")
async def handle_get_health(
    container: Annotated[WebContainer, Depends(get_container)],
) -> dict[str, Any]:
    """GET /api/health - Run live health checks against all production services."""
    return await container.health_service.check_all()


@router.get("/logs")
async def handle_get_logs(
    container: Annotated[WebContainer, Depends(get_container)],
) -> dict[str, Any]:
    """GET /api/logs - Return circular buffer of recent diagnostic events."""
    logs: list[dict[str, object]] = []
    if container.simulator_service:
        logs = list(reversed(container.simulator_service.logs))

    admin_alerts: list[dict[str, object]] = []
    if container.admin_notifier:
        admin_alerts = list(reversed(container.admin_notifier.recent_alerts))

    return {
        "current_status": (
            container.simulator_service.current_status if container.simulator_service else "ready"
        ),
        "last_error": (
            container.simulator_service.last_error if container.simulator_service else None
        ),
        "logs": logs,
        "admin_alerts": admin_alerts,
    }


# --------------------------------------------------------------------------
# Chats & Statistics
# --------------------------------------------------------------------------


@router.get("/chats")
async def handle_get_chats(
    container: Annotated[WebContainer, Depends(get_container)],
) -> dict[str, Any]:
    """GET /api/chats - List all available group chats for inspection."""
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
                            "created_at": rec.added_at.isoformat() if rec.added_at else None,
                            "is_simulator": rec.chat_id == SIMULATOR_CHAT_ID,
                        }
                    )
        except Exception as exc:
            logger.error("Failed to query chats from database", error=str(exc))

    if container.config.enable_simulator and not any(
        c["chat_id"] == SIMULATOR_CHAT_ID for c in chats
    ):
        chats.insert(
            0,
            {
                "chat_id": SIMULATOR_CHAT_ID,
                "title": "Dev Test Group (Simulator)",
                "created_at": None,
                "is_simulator": True,
            },
        )

    return {"chats": chats}


@router.get("/stats")
async def handle_get_stats(
    container: Annotated[WebContainer, Depends(get_container)],
    chat_id: Annotated[int | None, Query()] = None,
) -> dict[str, Any]:
    """GET /api/stats?chat_id=... - Return operational stats and checklist."""
    target_chat_id = (
        chat_id
        if chat_id is not None
        else (SIMULATOR_CHAT_ID if container.config.enable_simulator else None)
    )

    stats: dict[str, Any] = {
        "all_ready": container.health_service.all_ready,
        "checklist": container.health_service.items,
        "llm_model": f"OpenAI ({container.settings.openai_response_model})",
        "memory_backend": "Graphiti (Neo4j)",
        "bot_names": container.settings.bot_name_list or ["Bot"],
        "enable_simulator": container.config.enable_simulator,
        "memory_stats": {"status": "offline"},
    }

    if container.memory_query_service and target_chat_id is not None:
        metrics = await container.memory_query_service.get_stats(target_chat_id)
        stats.update(metrics)

    return stats


# --------------------------------------------------------------------------
# Knowledge Graph & Memory
# --------------------------------------------------------------------------


@router.get("/graph")
async def handle_get_graph(
    container: Annotated[WebContainer, Depends(get_container)],
    chat_id: Annotated[int | None, Query(description="Target chat id")] = None,
) -> Any:
    """GET /api/graph?chat_id=... - Return nodes and edges for Vis.js visualization."""
    if chat_id is None:
        return JSONResponse(
            status_code=400,
            content={"error": "chat_id query parameter is required"},
        )
    return await container.graph_service.get_graph(chat_id)


@router.get("/memories")
async def handle_get_memories(
    container: Annotated[WebContainer, Depends(get_container)],
    chat_id: Annotated[int | None, Query(description="Target chat id")] = None,
) -> Any:
    """GET /api/memories?chat_id=... - Return recent extracted facts."""
    if chat_id is None:
        return JSONResponse(
            status_code=400,
            content={"error": "chat_id query parameter is required"},
        )
    if not container.memory_query_service:
        return {"facts": []}

    facts = await container.memory_query_service.get_memories(chat_id)
    return {"facts": facts}


@router.get("/context")
async def handle_get_context(
    container: Annotated[WebContainer, Depends(get_container)],
    chat_id: Annotated[int | None, Query()] = None,
) -> Any:
    """GET /api/context?chat_id=... - Return current sliding context buffer."""
    target_chat_id = chat_id if chat_id is not None else SIMULATOR_CHAT_ID

    if not container.context_builder:
        return JSONResponse(
            status_code=503,
            content={"error": "Context service is unavailable"},
        )

    try:
        messages = await container.context_builder.get_context(target_chat_id)
        return {
            "messages": [
                {
                    "message_id": m.message_id,
                    "user_id": m.user_id,
                    "display_name": m.display_name,
                    "text": m.text,
                    "timestamp": m.timestamp.isoformat(),
                }
                for m in messages
            ]
        }
    except Exception:
        logger.exception("Failed to retrieve conversation context for chat_id=%s", target_chat_id)
        return JSONResponse(
            status_code=500,
            content={"error": "Failed to fetch conversation context"},
        )


# --------------------------------------------------------------------------
# Chat Simulator
# --------------------------------------------------------------------------


@router.get("/simulator/presets")
async def handle_get_presets(
    container: Annotated[WebContainer, Depends(get_container)],
) -> dict[str, Any]:
    """GET /api/simulator/presets - Return available test users and scenarios."""
    if not container.config.enable_simulator or not container.simulator_service:
        return {"users": [], "presets": []}

    return {
        "users": PRESET_USERS,
        "presets": container.simulator_service.get_presets(),
    }


@router.post("/simulator/send_message")
async def handle_send_message(
    payload: SimulateMessageRequest,
    container: Annotated[WebContainer, Depends(get_container)],
) -> Any:
    """POST /api/simulator/send_message - Process virtual message in sandbox."""
    if not container.config.enable_simulator or not container.simulator_service:
        return JSONResponse(
            status_code=403,
            content={"success": False, "error": "Simulator mode is disabled in this environment"},
        )

    text = payload.text.strip()
    if not text:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "Message text cannot be empty"},
        )

    try:
        return await container.simulator_service.send_simulated_message(
            user_id=payload.user_id,
            user_name=payload.user_name,
            text=text,
            reply_to_bot=payload.reply_to_bot,
        )
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(exc)},
        )
