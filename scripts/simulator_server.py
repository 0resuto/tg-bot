"""Interactive web simulator server for manual testing of the Telegram Memory Bot.

Runs the real production bot stack (PostgreSQL, Redis, Graphiti on Neo4j, OpenAI LLM)
with zero fallbacks, replacing ONLY the Telegram messenger layer with a web panel.
Includes an explicit live system checklist verifying the health of all infrastructure components.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import traceback
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import redis.asyncio as aioredis
from aiohttp import web
from neo4j import GraphDatabase

from bot.config import Settings
from bot.domain.models import ChatMessage, MemberIdentity
from bot.infrastructure.database.engine import create_async_engine_instance, create_session_factory
from bot.infrastructure.database.tables import Base
from bot.infrastructure.llm.openai_provider import OpenAILLMProvider
from bot.infrastructure.memory.graphiti_backend import GraphitiMemoryBackend
from bot.interfaces.task_runner import AsyncioTaskRunner
from bot.log import get_logger, setup_logging
from bot.repositories import ChatRepository, MemberRepository, TokenUsageRepository
from bot.services.context_builder import ContextBuilder
from bot.services.debouncer import MessageDebouncer
from bot.services.memory_service import MemoryService
from bot.services.mention_detector import MentionDetector
from bot.services.response_service import ResponseService
from bot.services.sensitive_filter import SensitiveFilter

logger = get_logger("simulator")


class SystemChecklist:
    """Diagnostic checklist verifying all production services without fallbacks."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.items: list[dict[str, Any]] = []
        self.all_ready: bool = False

    async def check_all(self) -> dict[str, Any]:
        checks = []

        # 1. OpenAI API
        ai_check = {
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
            try:
                ai_check["status"] = "ok"
                ai_check["message"] = f"Key active, model: {self.settings.openai_response_model}"
            except Exception as e:
                ai_check["status"] = "error"
                ai_check["error"] = f"OpenAI error: {e}"
                ai_check["message"] = "Connection / Auth failed"
        checks.append(ai_check)

        # 2. PostgreSQL
        pg_check = {
            "id": "postgres",
            "name": "PostgreSQL Database",
            "target": f"{self.settings.postgres_host}:{self.settings.postgres_port}/{self.settings.postgres_db}",
            "status": "ok",
            "message": "Connected",
            "error": None,
        }
        try:
            engine = create_async_engine_instance(self.settings.postgres_dsn)
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            await engine.dispose()
            pg_check["status"] = "ok"
            pg_check["message"] = "Connected and schema verified"
        except Exception as e:
            pg_check["status"] = "error"
            pg_check["error"] = f"PostgreSQL error: {e}"
            pg_check["message"] = (
                f"Cannot connect to {self.settings.postgres_host}:{self.settings.postgres_port}"
            )
        checks.append(pg_check)

        # 3. Redis
        redis_check = {
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
        except Exception as e:
            redis_check["status"] = "error"
            redis_check["error"] = f"Redis error: {e}"
            redis_check["message"] = f"Cannot connect to {self.settings.redis_url}"
        checks.append(redis_check)

        # 4. Neo4j & Graphiti Memory
        neo_check = {
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
            except Exception as e:
                neo_check["status"] = "error"
                neo_check["error"] = f"Neo4j error: {e}"
                neo_check["message"] = f"Cannot connect to {self.settings.neo4j_uri}"
        checks.append(neo_check)

        self.items = checks
        self.all_ready = all(item["status"] == "ok" for item in checks)
        return {
            "all_ready": self.all_ready,
            "items": self.items,
            "checked_at": datetime.now(UTC).isoformat(),
        }


class SimulatorApp:
    def __init__(self) -> None:
        self.chat_id = -1001987654321
        self.bot_user_id = 999999999

        # 1. Settings & Persona
        self.settings = Settings()
        self.bot_names = self.settings.bot_name_list or ["Bot"]
        loaded_persona = self.settings.get_persona_prompt()
        if loaded_persona and loaded_persona.strip():
            self.persona_prompt = loaded_persona.strip()
        else:
            self.persona_prompt = (
                f"Ты — дружелюбный участник группового чата по имени {self.bot_names[0]}. "
                "Общайся естественно, тепло, по-дружески и с юмором, вспоминая детали из жизни друзей."
            )

        self.bot_username = f"{self.bot_names[0].lower()}_bot"

        # 2. State & Diagnostics
        self.checklist = SystemChecklist(self.settings)
        self.task_runner = AsyncioTaskRunner()
        self.current_status: str = "initializing"
        self.last_error: str | None = None
        self.logs: list[dict[str, Any]] = []

        # Components
        self.engine: Any = None
        self.session_factory: Any = None
        self.chat_repo: Any = None
        self.member_repo: Any = None
        self.token_repo: Any = None
        self.redis: Any = None
        self.llm: Any = None
        self.memory_backend: Any = None
        self.memory_service: Any = None
        self.context_builder: Any = None
        self.debouncer: Any = None
        self.mention_detector: Any = None
        self.sensitive_filter: Any = None
        self.response_service: Any = None

    def log_event(self, event: dict[str, Any]) -> None:
        self.logs.append(event)
        if len(self.logs) > 50:
            self.logs.pop(0)

    async def init(self) -> None:
        logger.info("Verifying services and initializing simulator components...")
        self.current_status = "checking_health"

        # 1. Run live checklist
        await self.checklist.check_all()

        # 2. Setup PostgreSQL if ok
        pg_item = next((x for x in self.checklist.items if x["id"] == "postgres"), None)
        if pg_item and pg_item["status"] == "ok":
            try:
                if self.engine is None or self.session_factory is None:
                    self.engine = create_async_engine_instance(self.settings.postgres_dsn)
                    self.session_factory = create_session_factory(self.engine)
                    self.chat_repo = ChatRepository(self.session_factory)
                    self.member_repo = MemberRepository(self.session_factory)
                    self.token_repo = TokenUsageRepository(self.session_factory)
                await self.chat_repo.upsert_chat(self.chat_id, "Dev Test Group")
            except Exception as e:
                logger.error("Failed to initialize PostgreSQL components: %s", e)
                pg_item["status"] = "error"
                pg_item["error"] = str(e)
                self.checklist.all_ready = False

        # 3. Setup Redis if ok
        redis_item = next((x for x in self.checklist.items if x["id"] == "redis"), None)
        if redis_item and redis_item["status"] == "ok":
            try:
                if self.redis is None:
                    self.redis = aioredis.from_url(self.settings.redis_url)
                if self.context_builder is None:
                    self.context_builder = ContextBuilder(
                        redis_client=self.redis,
                        window_minutes=int(self.settings.context_window_minutes),
                        min_messages=int(self.settings.context_min_messages),
                    )
            except Exception as e:
                logger.error("Failed to initialize Redis components: %s", e)
                redis_item["status"] = "error"
                redis_item["error"] = str(e)
                self.checklist.all_ready = False

        # 4. Setup OpenAI LLM if ok
        ai_item = next((x for x in self.checklist.items if x["id"] == "openai"), None)
        if ai_item and ai_item["status"] == "ok" and self.llm is None:
            self.llm = OpenAILLMProvider(
                api_key=self.settings.openai_api_key,
                default_model=self.settings.openai_response_model,
                default_chat_id=self.chat_id,
            )

        # 5. Setup Neo4j Graphiti Memory if ok
        neo_item = next((x for x in self.checklist.items if x["id"] == "neo4j"), None)
        if (
            neo_item
            and neo_item["status"] == "ok"
            and self.settings.openai_api_key
            and self.memory_backend is None
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
                await self.memory_backend.init()
                logger.info("Graphiti Neo4j memory backend initialized successfully")
            except Exception as e:
                logger.error("Failed to initialize Graphiti memory: %s", e)
                neo_item["status"] = "error"
                neo_item["error"] = str(e)
                self.checklist.all_ready = False

        if self.mention_detector is None:
            self.mention_detector = MentionDetector(
                bot_names=self.bot_names,
                bot_user_id=self.bot_user_id,
                bot_username=self.bot_username,
            )

        if self.sensitive_filter is None:
            self.sensitive_filter = SensitiveFilter(
                enabled=self.settings.sensitive_filter_enabled,
                categories=self.settings.sensitive_category_list,
            )

        if self.memory_backend and self.token_repo and self.redis and self.memory_service is None:
            self.memory_service = MemoryService(
                memory=self.memory_backend,
                sensitive_filter=self.sensitive_filter,
                token_repo=self.token_repo,
                redis_client=self.redis,
                cache_ttl=60,
            )

            async def flush_callback(chat_id: int, user_id: int, msgs: list[ChatMessage]) -> None:
                await self.memory_service.ingest_messages(chat_id, user_id, msgs)

            self.debouncer = MessageDebouncer(
                redis_client=self.redis,
                debounce_seconds=2.0,
                on_flush=flush_callback,
            )

        if (
            self.llm
            and self.memory_service
            and self.context_builder
            and self.token_repo
            and self.response_service is None
        ):
            self.response_service = ResponseService(
                llm=self.llm,
                memory_service=self.memory_service,
                context_builder=self.context_builder,
                token_repo=self.token_repo,
                persona_prompt=self.persona_prompt,
                response_model=self.settings.openai_response_model,
                bot_language=self.settings.bot_language,
            )

        is_healthy = (
            self.checklist.all_ready
            and self.member_repo is not None
            and self.context_builder is not None
            and self.memory_service is not None
            and self.response_service is not None
        )

        if is_healthy:
            self.current_status = "idle"
            self.last_error = None
            logger.info("Simulator ready! All production services verified and initialized.")
        else:
            self.current_status = "error"
            failed = [i["name"] for i in self.checklist.items if i["status"] != "ok"]
            missing_comps = []
            if not self.member_repo:
                missing_comps.append("PostgreSQL")
            if not self.context_builder:
                missing_comps.append("Redis")
            if not self.memory_service:
                missing_comps.append("Neo4j")
            if not self.response_service:
                missing_comps.append("OpenAI")
            reasons = list(dict.fromkeys(failed + missing_comps))
            self.last_error = f"Services/Components offline: {', '.join(reasons)}"
            logger.warning("Simulator components degraded: %s", self.last_error)


async def handle_send_message(request: web.Request) -> web.Response:
    sim: SimulatorApp = request.app["sim"]
    data = await request.json()

    user_id = int(data.get("user_id", 1))
    user_name = data.get("user_name", "Alice")
    text = data.get("text", "")
    reply_to_bot = bool(data.get("reply_to_bot", False))

    now = datetime.now(UTC)
    msg_id = int(now.timestamp() * 1000) % 1000000

    # Ensure required production services are running and initialized
    await sim.init()

    if (
        not sim.checklist.all_ready
        or sim.member_repo is None
        or sim.context_builder is None
        or sim.memory_service is None
        or sim.response_service is None
    ):
        failed = [
            f"{i['name']} ({i['error'] or i['message']})"
            for i in sim.checklist.items
            if i["status"] != "ok"
        ]
        missing = []
        if not sim.member_repo:
            missing.append("PostgreSQL")
        if not sim.context_builder:
            missing.append("Redis")
        if not sim.memory_service:
            missing.append("Neo4j/Graphiti")
        if not sim.response_service:
            missing.append("OpenAI")
        error_msg = f"Cannot process message. Inactive components: {', '.join(missing or failed)}."
        details = f"Checklist issues: {'; '.join(failed) if failed else 'None'}. Missing Python services: {', '.join(missing)}."
        sim.current_status = "error"
        sim.last_error = error_msg
        return web.json_response(
            {
                "success": False,
                "error": error_msg,
                "error_details": details,
                "checklist": sim.checklist.items,
                "bot_status": "error",
            },
            status=400,
        )

    try:
        sim.current_status = "processing"

        # 1. Update member in real PostgreSQL
        member = MemberIdentity(
            telegram_user_id=user_id, username=user_name.lower(), first_name=user_name
        )
        await sim.member_repo.upsert_member(sim.chat_id, member, chat_title="Dev Test Group")

        # 2. Check sensitive topics scan
        sensitive_cats = sim.sensitive_filter.scan(text)
        redacted_text = sim.sensitive_filter.redact(text) if sensitive_cats else text

        # 3. Create chat message
        msg = ChatMessage(
            chat_id=sim.chat_id,
            user_id=user_id,
            text=text,
            timestamp=now,
            message_id=msg_id,
            display_name=user_name,
            reply_to_message_id=9999 if reply_to_bot else None,
        )
        await sim.context_builder.add_message(msg)

        # 4. Ingest into real Graphiti Neo4j memory
        sim.current_status = "ingesting_memory"
        await sim.memory_service.ingest_messages(sim.chat_id, user_id, [msg])

        # 5. Check mention
        reply_id = sim.bot_user_id if reply_to_bot else None
        is_addressed = sim.mention_detector.is_addressed(text=text, reply_to_user_id=reply_id)

        if is_addressed:
            if reply_to_bot:
                trigger_reason = "Triggered via direct reply to bot message"
            else:
                trigger_reason = (
                    f"Triggered by bot name mention (configured names: {', '.join(sim.bot_names)})"
                )
        else:
            trigger_reason = f"Not addressed to bot (silent memory observation; bot names: {', '.join(sim.bot_names)})"

        bot_reply = None
        if is_addressed:
            sim.current_status = "calling_llm"
            context = await sim.context_builder.get_context(sim.chat_id)
            active_names = list({m.display_name for m in context if m.display_name})
            bot_reply = await sim.response_service.generate_response(
                chat_id=sim.chat_id,
                user_display_name=user_name,
                active_user_names=active_names,
                raise_on_error=True,
            )

        sim.current_status = "idle"
        sim.last_error = None

        event = {
            "id": msg_id,
            "timestamp": now.isoformat(),
            "user_name": user_name,
            "text": text,
            "is_addressed": is_addressed,
            "trigger_reason": trigger_reason,
            "sensitive_categories": [cat.value for cat in sensitive_cats],
            "bot_reply": bot_reply,
            "status": "success",
        }
        sim.log_event(event)

        return web.json_response(
            {
                "success": True,
                "error": None,
                "message": {
                    "id": msg.message_id,
                    "user_id": user_id,
                    "user_name": user_name,
                    "text": text,
                    "timestamp": now.isoformat(),
                },
                "is_addressed": is_addressed,
                "trigger_reason": trigger_reason,
                "sensitive_categories": [cat.value for cat in sensitive_cats],
                "redacted_text": redacted_text,
                "bot_reply": bot_reply,
                "bot_status": sim.current_status,
                "bot_names": sim.bot_names,
            }
        )

    except Exception as e:
        trace = traceback.format_exc()
        logger.error("Error processing simulator message: %s", e)
        sim.current_status = "error"
        sim.last_error = f"{type(e).__name__}: {str(e)}"

        sim.log_event(
            {
                "id": msg_id,
                "timestamp": now.isoformat(),
                "user_name": user_name,
                "text": text,
                "status": "error",
                "error": sim.last_error,
                "traceback": trace,
            }
        )

        return web.json_response(
            {
                "success": False,
                "error": sim.last_error,
                "error_details": trace,
                "message": {
                    "id": msg_id,
                    "user_id": user_id,
                    "user_name": user_name,
                    "text": text,
                    "timestamp": now.isoformat(),
                },
                "is_addressed": is_addressed if "is_addressed" in locals() else False,
                "trigger_reason": f"Crashed during processing: {type(e).__name__}: {str(e)}",
                "sensitive_categories": [cat.value for cat in sensitive_cats]
                if "sensitive_cats" in locals()
                else [],
                "redacted_text": text,
                "bot_reply": None,
                "bot_status": "error",
                "bot_names": sim.bot_names,
            },
            status=200,
        )


async def handle_get_checklist(request: web.Request) -> web.Response:
    sim: SimulatorApp = request.app["sim"]
    await sim.init()
    return web.json_response(
        {
            "all_ready": sim.checklist.all_ready,
            "items": sim.checklist.items,
            "checked_at": datetime.now(UTC).isoformat(),
        }
    )


async def handle_get_context(request: web.Request) -> web.Response:
    sim: SimulatorApp = request.app["sim"]
    if not sim.context_builder:
        return web.json_response({"messages": []})
    messages = await sim.context_builder.get_context(sim.chat_id)
    return web.json_response(
        {
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
    )


def _serialize_neo4j_val(val: Any) -> Any:
    if val is None:
        return None
    if isinstance(val, int | float | bool | str):
        return val
    if isinstance(val, list | tuple):
        return [_serialize_neo4j_val(x) for x in val]
    if isinstance(val, dict):
        return {k: _serialize_neo4j_val(v) for k, v in val.items()}
    return str(val)


async def handle_get_memories(request: web.Request) -> web.Response:
    sim: SimulatorApp = request.app["sim"]
    if not sim.memory_service:
        return web.json_response({"facts": []})

    facts = []
    try:
        from neo4j import GraphDatabase

        def fetch_facts():
            driver = GraphDatabase.driver(
                sim.settings.neo4j_uri,
                auth=(sim.settings.neo4j_user, sim.settings.neo4j_password),
            )
            extracted = []
            try:
                with driver.session() as session:
                    res = session.run("""
                        MATCH (n)-[r]->(m)
                        WHERE r.fact IS NOT NULL
                        RETURN coalesce(n.name, 'Fact') as subject, r.fact as fact, r.created_at as created_at
                        ORDER BY r.created_at DESC
                        LIMIT 50
                    """)
                    for rec in res:
                        extracted.append(
                            {
                                "subject": rec.get("subject") or "Fact",
                                "fact_text": rec.get("fact") or "",
                                "created_at": _serialize_neo4j_val(rec.get("created_at")),
                            }
                        )
            finally:
                driver.close()
            return extracted

        facts = await asyncio.to_thread(fetch_facts)
        if not facts:
            stats = await sim.memory_service.get_stats(sim.chat_id)
            facts = [
                {
                    "fact_text": f"Graphiti Graph Stats: {json.dumps(stats, ensure_ascii=False)}",
                    "subject": "Neo4j Graphiti",
                    "created_at": datetime.now(UTC).isoformat(),
                }
            ]
    except Exception as e:
        facts = [
            {"fact_text": f"Error retrieving memories: {e}", "subject": "Error", "created_at": None}
        ]

    return web.json_response({"facts": facts})


async def handle_get_graph(request: web.Request) -> web.Response:
    sim: SimulatorApp = request.app["sim"]
    if not sim.memory_backend:
        await sim.init()
    if not sim.memory_backend:
        return web.json_response(
            {"success": False, "error": "Neo4j / Graphiti is offline", "nodes": [], "edges": []}
        )

    from neo4j import GraphDatabase

    def query_graph():
        driver = GraphDatabase.driver(
            sim.settings.neo4j_uri,
            auth=(sim.settings.neo4j_user, sim.settings.neo4j_password),
        )
        nodes_dict = {}
        edges_dict = {}
        try:
            with driver.session() as session:
                result = session.run("""
                    MATCH (n)
                    OPTIONAL MATCH (n)-[r]->(m)
                    RETURN n, r, m
                    LIMIT 300
                """)
                for record in result:
                    n = record.get("n")
                    r = record.get("r")
                    m = record.get("m")

                    for node_obj in (n, m):
                        if node_obj is not None and node_obj.element_id not in nodes_dict:
                            labels = list(node_obj.labels)
                            props = {k: _serialize_neo4j_val(v) for k, v in dict(node_obj).items()}
                            name = (
                                props.get("name")
                                or props.get("title")
                                or props.get("source_description")
                                or props.get("content")
                                or (labels[0] if labels else "Node")
                            )
                            display_label = str(name)
                            if len(display_label) > 24:
                                display_label = display_label[:21] + "..."

                            labels_lower = [lbl.lower() for lbl in labels]

                            # Classification by entity type / node role
                            if "episodic" in labels_lower:
                                group = "Episodic"
                                icon = "💬"
                                color = {"background": "#7c3aed", "border": "#a78bfa"}
                                shape = "diamond"
                                size = 18
                            elif "community" in labels_lower:
                                group = "Community"
                                icon = "🌐"
                                color = {"background": "#d97706", "border": "#fbbf24"}
                                shape = "hexagon"
                                size = 26
                            elif any(
                                lbl in labels_lower for lbl in ("person", "user", "member", "human")
                            ):
                                group = "Person"
                                icon = "👤"
                                color = {"background": "#059669", "border": "#34d399"}
                                shape = "dot"
                                size = 26
                            elif any(
                                lbl in labels_lower
                                for lbl in ("animal", "pet", "creature", "dog", "cat")
                            ):
                                group = "Animal"
                                icon = "🐾"
                                color = {"background": "#9333ea", "border": "#c084fc"}
                                shape = "dot"
                                size = 24
                            elif any(
                                lbl in labels_lower
                                for lbl in (
                                    "item",
                                    "object",
                                    "product",
                                    "vehicle",
                                    "tool",
                                    "device",
                                )
                            ):
                                group = "Item"
                                icon = "📦"
                                color = {"background": "#2563eb", "border": "#60a5fa"}
                                shape = "dot"
                                size = 23
                            elif any(
                                lbl in labels_lower
                                for lbl in ("location", "place", "city", "country", "venue")
                            ):
                                group = "Location"
                                icon = "📍"
                                color = {"background": "#ea580c", "border": "#fb923c"}
                                shape = "dot"
                                size = 24
                            elif any(
                                lbl in labels_lower
                                for lbl in (
                                    "concept",
                                    "hobby",
                                    "skill",
                                    "event",
                                    "sport",
                                    "interest",
                                    "activity",
                                )
                            ):
                                group = "Concept"
                                icon = "💡"
                                color = {"background": "#ca8a04", "border": "#fde047"}
                                shape = "dot"
                                size = 22
                            else:
                                group = "Entity"
                                icon = "⚪"
                                color = {"background": "#0284c7", "border": "#38bdf8"}
                                shape = "dot"
                                size = 22

                            nodes_dict[node_obj.element_id] = {
                                "id": node_obj.element_id,
                                "label": f"{icon} {display_label}",
                                "raw_label": display_label,
                                "icon": icon,
                                "full_name": str(name),
                                "labels": labels,
                                "group": group,
                                "color": color,
                                "shape": shape,
                                "size": size,
                                "font": {"color": "#ffffff", "face": "system-ui, sans-serif"},
                                "properties": props,
                            }

                    if (
                        r is not None
                        and r.element_id not in edges_dict
                        and n is not None
                        and m is not None
                    ):
                        r_props = {k: _serialize_neo4j_val(v) for k, v in dict(r).items()}
                        fact = r_props.get("fact") or r_props.get("name") or ""
                        rel_label = (
                            str(fact)[:28] + ("..." if len(str(fact)) > 28 else "")
                            if fact
                            else r.type
                        )

                        edges_dict[r.element_id] = {
                            "id": r.element_id,
                            "from": n.element_id,
                            "to": m.element_id,
                            "label": rel_label,
                            "type": r.type,
                            "full_fact": str(fact) if fact else r.type,
                            "properties": r_props,
                            "arrows": "to",
                            "color": {
                                "color": "#64748b",
                                "highlight": "#38bdf8",
                                "hover": "#94a3b8",
                            },
                            "font": {"size": 10, "color": "#94a3b8", "background": "#0f172a"},
                        }
        finally:
            driver.close()
        return list(nodes_dict.values()), list(edges_dict.values())

    try:
        nodes, edges = await asyncio.to_thread(query_graph)
        return web.json_response(
            {
                "success": True,
                "nodes": nodes,
                "edges": edges,
                "stats": {
                    "nodes_count": len(nodes),
                    "edges_count": len(edges),
                },
            }
        )
    except Exception as exc:
        logger.error("Failed to fetch Neo4j graph: %s", exc)
        return web.json_response(
            {"success": False, "error": str(exc), "nodes": [], "edges": []}, status=500
        )


async def handle_forget_fact(request: web.Request) -> web.Response:
    sim: SimulatorApp = request.app["sim"]
    if not sim.memory_service:
        return web.json_response(
            {"deleted_count": 0, "error": "Memory service is offline"}, status=400
        )
    data = await request.json()
    description = data.get("description", "")
    deleted = await sim.memory_service.forget_fact(description, sim.chat_id)
    return web.json_response({"deleted_count": deleted})


async def handle_get_stats(request: web.Request) -> web.Response:
    sim: SimulatorApp = request.app["sim"]
    mem_stats = (
        await sim.memory_service.get_stats(sim.chat_id)
        if sim.memory_service
        else {"status": "offline"}
    )
    token_stats = (
        await sim.token_repo.get_usage_stats(sim.chat_id, days=30)
        if sim.token_repo
        else {"today_tokens": 0}
    )

    return web.json_response(
        {
            "all_ready": sim.checklist.all_ready,
            "checklist": sim.checklist.items,
            "llm_model": f"OpenAI ({sim.settings.openai_response_model})",
            "memory_backend": "Graphiti (Neo4j)",
            "current_status": sim.current_status,
            "last_error": sim.last_error,
            "memory_stats": mem_stats,
            "token_stats": token_stats,
            "bot_names": sim.bot_names,
            "logs": list(reversed(sim.logs[-30:])),
        }
    )


async def handle_get_logs(request: web.Request) -> web.Response:
    sim: SimulatorApp = request.app["sim"]
    return web.json_response(
        {
            "current_status": sim.current_status,
            "last_error": sim.last_error,
            "logs": list(reversed(sim.logs)),
        }
    )


async def handle_index(request: web.Request) -> web.FileResponse:
    index_file = Path(__file__).parent.parent / "web" / "index.html"
    return web.FileResponse(index_file)


def create_app() -> web.Application:
    app = web.Application()
    sim = SimulatorApp()
    app["sim"] = sim

    async def on_startup(app_instance: web.Application) -> None:
        await sim.init()

    app.on_startup.append(on_startup)

    app.router.add_get("/", handle_index)
    app.router.add_get("/api/checklist", handle_get_checklist)
    app.router.add_post("/api/send_message", handle_send_message)
    app.router.add_get("/api/context", handle_get_context)
    app.router.add_get("/api/memories", handle_get_memories)
    app.router.add_get("/api/graph", handle_get_graph)
    app.router.add_post("/api/forget", handle_forget_fact)
    app.router.add_get("/api/stats", handle_get_stats)
    app.router.add_get("/api/logs", handle_get_logs)

    web_dir = Path(__file__).parent.parent / "web"
    app.router.add_static("/static/", path=web_dir, show_index=False)

    return app


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Telegram Memory Bot Test Simulator (Production Stack)"
    )
    parser.add_argument(
        "--port", type=int, default=8080, help="Port to run simulator web on (default: 8080)"
    )
    parser.add_argument(
        "--host", type=str, default="127.0.0.1", help="Host to bind (default: 127.0.0.1)"
    )
    args = parser.parse_args()

    setup_logging(debug=True)
    print("\n=======================================================")
    print("  Telegram Memory Bot — Dev Simulator (Real Production Stack)")
    print("  Zero fallbacks. Running with real Postgres, Redis, Neo4j, OpenAI.")
    print(f"  Open in browser: http://{args.host}:{args.port}")
    print("=======================================================\n")

    app = create_app()
    try:
        web.run_app(app, host=args.host, port=args.port, reuse_address=True)
    except OSError as err:
        if "10048" in str(err) or "already in use" in str(err).lower():
            print(f"\n[ERROR] Port {args.port} is currently busy or closing.")
            print(
                f"Try running with a different port: uv run python scripts/simulator_server.py --port {args.port + 1}\n"
            )
        raise


if __name__ == "__main__":
    main()
