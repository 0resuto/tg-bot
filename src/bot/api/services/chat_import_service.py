"""Background service orchestrating chat history imports from the web dashboard."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from bot.log import get_logger
from bot.services.message_filter import MessageNoiseFilter

try:
    from tools.chat_importer.chunker import ConversationChunker
    from tools.chat_importer.parser import TelegramExportParser
    from tools.chat_importer.pipeline import ImportPipeline
except ModuleNotFoundError:
    import sys
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[4]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from tools.chat_importer.chunker import ConversationChunker
    from tools.chat_importer.parser import TelegramExportParser
    from tools.chat_importer.pipeline import ImportPipeline

if TYPE_CHECKING:
    from bot.api.dependencies import WebContainer
    from bot.config import Settings

logger = get_logger(__name__)


class ChatImportService:
    """Manages chat history parsing, dry-run previews, and background ingestion."""

    def __init__(self, settings: Settings, container: WebContainer) -> None:
        self.settings = settings
        self.container = container
        self.parser = TelegramExportParser()
        self.noise_filter = MessageNoiseFilter()

        # State tracking
        self.status: str = "idle"  # idle, running, completed, failed
        self.total_episodes: int = 0
        self.processed_episodes: int = 0
        self.current_stage: str = "Idle"
        self.error: str | None = None
        self.started_at: str | None = None
        self.finished_at: str | None = None
        self.last_summary: dict[str, Any] | None = None

        self._task: asyncio.Task[None] | None = None

    def generate_preview(
        self,
        data: dict[str, Any],
        chat_id: int | None = None,
        gap_minutes: int = 20,
        max_messages: int = 15,
        min_length: int | None = None,
    ) -> dict[str, Any]:
        """Perform fast dry-run analysis on chat export payload without modifying databases."""
        if min_length is not None:
            self.noise_filter.min_length = min_length

        parsed = self.parser.parse_dict(
            data=data,
            chat_id=chat_id,
            fallback_chat_id=self.settings.group_chat_id,
        )

        total_raw = len(parsed.messages)
        meaningful = self.noise_filter.filter_batch(parsed.messages)
        dropped_count = total_raw - len(meaningful)
        noise_pct = round((dropped_count / total_raw * 100), 1) if total_raw > 0 else 0.0

        chunker = ConversationChunker(gap_minutes=gap_minutes, max_messages=max_messages)
        episodes = chunker.chunk(meaningful)

        # Sample preview of first 3 episodes
        sample_episodes = [
            {
                "episode_index": ep.episode_index,
                "source_user_name": ep.source_user_name,
                "reference_time": ep.reference_time.isoformat(),
                "messages_count": len(ep.messages),
                "text": ep.text,
            }
            for ep in episodes[:3]
        ]

        members_preview = [
            {
                "user_id": m.telegram_user_id,
                "display_name": m.display_name,
            }
            for m in parsed.members[:25]
        ]

        return {
            "chat_id": parsed.chat_id,
            "chat_title": parsed.chat_title,
            "total_raw_messages": total_raw,
            "meaningful_messages": len(meaningful),
            "dropped_noise_messages": dropped_count,
            "noise_percentage": noise_pct,
            "total_episodes": len(episodes),
            "members_count": len(parsed.members),
            "members": members_preview,
            "sample_episodes": sample_episodes,
        }

    async def start_import(
        self,
        data: dict[str, Any],
        chat_id: int | None = None,
        gap_minutes: int = 20,
        max_messages: int = 15,
        delay: float = 0.5,
        no_db: bool = False,
        min_length: int | None = None,
    ) -> dict[str, Any]:
        """Trigger background ingestion task for chat export data."""
        if self.status == "running":
            raise RuntimeError("An import task is already running.")

        self.status = "running"
        self.error = None
        self.total_episodes = 0
        self.processed_episodes = 0
        self.current_stage = "Initializing import pipeline..."
        self.started_at = datetime.now(UTC).isoformat()
        self.finished_at = None

        self._task = asyncio.create_task(
            self._run_import_task(
                data=data,
                chat_id=chat_id,
                gap_minutes=gap_minutes,
                max_messages=max_messages,
                delay=delay,
                no_db=no_db,
                min_length=min_length,
            ),
            name="chat_history_import_task",
        )

        return self.get_status()

    async def _run_import_task(
        self,
        data: dict[str, Any],
        chat_id: int | None,
        gap_minutes: int,
        max_messages: int,
        delay: float,
        no_db: bool,
        min_length: int | None,
    ) -> None:
        """Internal worker executing episodic ingestion with live progress updates."""
        try:
            self.current_stage = "Parsing chat export..."
            if min_length is not None:
                self.noise_filter.min_length = min_length

            parsed = self.parser.parse_dict(
                data=data,
                chat_id=chat_id,
                fallback_chat_id=self.settings.group_chat_id,
            )

            # Sync members if enabled
            if not no_db:
                if not self.container.member_repo:
                    try:
                        from bot.db.engine import (
                            create_async_engine_instance,
                            create_session_factory,
                        )
                        from bot.db.repository import MemberRepository

                        engine = create_async_engine_instance(self.settings.postgres_dsn)
                        session_factory = create_session_factory(engine)
                        self.container.member_repo = MemberRepository(session_factory)
                    except Exception as exc:
                        logger.warning(
                            "Could not lazily initialize MemberRepository for member sync",
                            exc_info=exc,
                        )

                if self.container.member_repo:
                    self.current_stage = "Synchronizing chat members to database..."
                    pipeline = ImportPipeline(
                        member_repo=self.container.member_repo,
                        memory_backend=self.container.memory_backend,
                        settings=self.settings,
                    )
                    await pipeline.sync_members(parsed, dry_run=False)

            self.current_stage = "Filtering noise and chunking conversations..."
            meaningful = self.noise_filter.filter_batch(parsed.messages)
            chunker = ConversationChunker(gap_minutes=gap_minutes, max_messages=max_messages)
            episodes = chunker.chunk(meaningful)

            self.total_episodes = len(episodes)
            self.processed_episodes = 0

            if not episodes:
                self.status = "completed"
                self.current_stage = "Finished: No meaningful episodes found to ingest."
                self.finished_at = datetime.now(UTC).isoformat()
                return

            memory_backend = self.container.memory_backend
            if not memory_backend:
                if self.settings.neo4j_password and self.settings.openai_api_key:
                    try:
                        self.current_stage = "Connecting to Graphiti Neo4j backend..."
                        from bot.db.graphiti import GraphitiMemoryBackend

                        memory_backend = GraphitiMemoryBackend(
                            neo4j_uri=self.settings.neo4j_uri,
                            neo4j_user=self.settings.neo4j_user,
                            neo4j_password=self.settings.neo4j_password,
                            openai_api_key=self.settings.openai_api_key,
                            extraction_model=self.settings.openai_extraction_model,
                            embedding_model=self.settings.openai_embedding_model,
                        )
                        self.container.memory_backend = memory_backend
                    except Exception as exc:
                        raise RuntimeError(
                            f"Failed to connect to Graphiti Neo4j backend: {exc}"
                        ) from exc
                else:
                    raise RuntimeError(
                        "Graphiti memory backend is offline or unconfigured. Verify NEO4J_PASSWORD and OPENAI_API_KEY in .env."
                    )

            self.current_stage = "Ingesting episodes into knowledge graph..."
            for idx, ep in enumerate(episodes, start=1):
                self.current_stage = f"Ingesting episode {idx} of {len(episodes)}..."
                await memory_backend.ingest_episode(
                    text=ep.text,
                    group_id=str(ep.chat_id),
                    source_user_name=ep.source_user_name,
                    reference_time=ep.reference_time,
                )
                self.processed_episodes = idx
                if delay > 0:
                    await asyncio.sleep(delay)

            self.status = "completed"
            self.current_stage = f"Successfully imported {len(episodes)} episodes."
            self.finished_at = datetime.now(UTC).isoformat()
            self.last_summary = {
                "chat_id": parsed.chat_id,
                "chat_title": parsed.chat_title,
                "total_episodes": len(episodes),
                "messages_ingested": len(meaningful),
            }

        except asyncio.CancelledError:
            self.status = "idle"
            self.current_stage = "Import cancelled by user."
            self.finished_at = datetime.now(UTC).isoformat()
            logger.info("Chat history import task was cancelled")
        except Exception as exc:
            self.status = "failed"
            self.error = str(exc)
            self.current_stage = f"Failed with error: {exc}"
            self.finished_at = datetime.now(UTC).isoformat()
            logger.error("Chat history import task failed", exc_info=exc)

    def get_status(self) -> dict[str, Any]:
        """Return current status and progress metrics."""
        percent = 0.0
        if self.total_episodes > 0:
            percent = round((self.processed_episodes / self.total_episodes) * 100, 1)

        return {
            "status": self.status,
            "total_episodes": self.total_episodes,
            "processed_episodes": self.processed_episodes,
            "progress_percent": percent,
            "current_stage": self.current_stage,
            "error": self.error,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "last_summary": self.last_summary,
        }

    def cancel_import(self) -> dict[str, Any]:
        """Cancel running import task if active."""
        if self._task and not self._task.done():
            self._task.cancel()
            self.status = "idle"
            self.current_stage = "Cancelling import task..."
            return {"cancelled": True, "message": "Import task cancellation requested."}
        return {"cancelled": False, "message": "No active import task to cancel."}
