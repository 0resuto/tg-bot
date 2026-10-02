"""Import pipeline orchestrator for Telegram chat history ingestion.

Coordinates parsing, noise filtering, database member synchronization,
conversation chunking, state checkpointing, and Graphiti knowledge graph ingestion.
"""

from __future__ import annotations

import asyncio
import json
import tempfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from bot.config import Settings
from bot.db.repository import MemberRepository
from bot.log import get_logger
from bot.models import MemoryBackend
from bot.services.message_filter import MessageNoiseFilter, default_noise_filter
from tools.chat_importer.chunker import ConversationChunker
from tools.chat_importer.contracts import CheckpointStateContract
from tools.chat_importer.parser import ParsedChatExport, TelegramExportParser

logger = get_logger(__name__)


@dataclass
class ImportCheckpoint:
    """State snapshot for resuming interrupted chat imports."""

    chat_id: int
    chat_title: str
    export_file: str
    total_episodes: int = 0
    processed_indices: list[int] = field(default_factory=list)
    last_processed_index: int = -1
    completed: bool = False
    updated_at: str = ""

    def mark_episode_done(self, index: int) -> None:
        """Record completed episode index."""
        if index not in self.processed_indices:
            self.processed_indices.append(index)
        self.last_processed_index = max(self.last_processed_index, index)
        self.updated_at = datetime.now(UTC).isoformat()
        if self.total_episodes > 0 and len(self.processed_indices) >= self.total_episodes:
            self.completed = True

    def save(self, file_path: Path) -> None:
        """Atomically persist checkpoint JSON to disk."""
        contract = CheckpointStateContract(
            chat_id=self.chat_id,
            chat_title=self.chat_title,
            export_file=self.export_file,
            total_episodes=self.total_episodes,
            processed_indices=self.processed_indices,
            last_processed_index=self.last_processed_index,
            completed=self.completed,
            updated_at=self.updated_at,
        )
        data = contract.model_dump()
        parent_dir = file_path.parent
        parent_dir.mkdir(parents=True, exist_ok=True)

        # Write to temporary file first then replace atomically
        with tempfile.NamedTemporaryFile(
            mode="w",
            dir=str(parent_dir),
            delete=False,
            encoding="utf-8",
            suffix=".tmp",
        ) as tmp:
            json.dump(data, tmp, indent=2, ensure_ascii=False)
            tmp_name = tmp.name

        Path(tmp_name).replace(file_path)

    @classmethod
    def load(cls, file_path: Path) -> ImportCheckpoint | None:
        """Load checkpoint from disk if present and valid."""
        if not file_path.is_file():
            return None
        try:
            with file_path.open("r", encoding="utf-8") as f:
                content = f.read()
            contract = CheckpointStateContract.model_validate_json(content)
            return cls(
                chat_id=contract.chat_id,
                chat_title=contract.chat_title,
                export_file=contract.export_file,
                total_episodes=contract.total_episodes,
                processed_indices=list(contract.processed_indices),
                last_processed_index=contract.last_processed_index,
                completed=contract.completed,
                updated_at=contract.updated_at,
            )
        except Exception as exc:
            logger.warning("Failed to validate checkpoint file; treating as fresh", error=str(exc))
            return None


@dataclass(frozen=True, slots=True)
class ImportSummary:
    """Execution metrics and results summary from import pipeline."""

    chat_id: int
    chat_title: str
    total_raw_messages: int
    meaningful_messages: int
    dropped_noise_messages: int
    members_synced: int
    total_episodes: int
    processed_episodes: int
    skipped_episodes: int
    dry_run: bool
    completed: bool


class ImportPipeline:
    """Orchestrates end-to-end processing of chat history into memory."""

    def __init__(
        self,
        parser: TelegramExportParser | None = None,
        noise_filter: MessageNoiseFilter | None = None,
        chunker: ConversationChunker | None = None,
        member_repo: MemberRepository | None = None,
        memory_backend: MemoryBackend | None = None,
        settings: Settings | None = None,
        state_dir: Path | None = None,
    ) -> None:
        self.parser = parser or TelegramExportParser()
        self.noise_filter = noise_filter or default_noise_filter
        self.chunker = chunker or ConversationChunker()
        self.member_repo = member_repo
        self.memory_backend = memory_backend
        self.settings = settings or Settings()
        self.state_dir = state_dir or Path.cwd()

    def get_checkpoint_path(self, chat_id: int) -> Path:
        """Resolve path to checkpoint file for given chat ID."""
        return self.state_dir / f".import_state_{chat_id}.json"

    async def sync_members(
        self,
        parsed: ParsedChatExport,
        dry_run: bool = False,
    ) -> int:
        """Upsert chat and member identities to database."""
        if not self.member_repo:
            logger.debug("Member repository not configured; skipping database sync")
            return 0

        if dry_run:
            logger.info(
                "Dry-run: Would sync chat members to database",
                chat_id=parsed.chat_id,
                chat_title=parsed.chat_title,
                members_count=len(parsed.members),
            )
            return len(parsed.members)

        synced_count = 0
        for member in parsed.members:
            try:
                await self.member_repo.upsert_member(
                    chat_id=parsed.chat_id,
                    member=member,
                    chat_title=parsed.chat_title,
                )
                synced_count += 1
            except Exception as exc:
                logger.error(
                    "Failed to upsert chat member",
                    user_id=member.telegram_user_id,
                    chat_id=parsed.chat_id,
                    error=str(exc),
                )

        logger.info(
            "Database member sync finished",
            chat_id=parsed.chat_id,
            members_synced=synced_count,
            total_members=len(parsed.members),
        )
        return synced_count

    async def run(
        self,
        file_path: str | Path,
        chat_id: int | None = None,
        dry_run: bool = False,
        resume: bool = False,
        gap_minutes: int = 20,
        max_messages: int = 15,
        delay: float = 0.0,
        no_db: bool = False,
        min_length: int | None = None,
    ) -> ImportSummary:
        """Execute full pipeline for chat export file."""
        resolved_file = Path(file_path).resolve()
        logger.info("Starting chat import pipeline", file=str(resolved_file), dry_run=dry_run)

        # 1. Parse export file
        parsed = self.parser.parse_file(
            file_path=resolved_file,
            chat_id=chat_id,
            fallback_chat_id=self.settings.group_chat_id,
        )

        # 2. Sync members to PostgreSQL if enabled
        members_synced = 0
        if not no_db:
            members_synced = await self.sync_members(parsed, dry_run=dry_run)
        else:
            logger.info("Database sync skipped (--no-db active)")

        # 3. Apply noise filtering
        if min_length is not None:
            self.noise_filter.min_length = min_length

        total_raw = len(parsed.messages)
        meaningful_messages = self.noise_filter.filter_batch(parsed.messages)
        dropped_count = total_raw - len(meaningful_messages)

        logger.info(
            "Noise filter applied",
            raw_count=total_raw,
            meaningful_count=len(meaningful_messages),
            dropped_noise=dropped_count,
        )

        # 4. Chunk messages into dialogue episodes
        chunker = ConversationChunker(gap_minutes=gap_minutes, max_messages=max_messages)
        episodes = chunker.chunk(meaningful_messages)

        if not episodes:
            logger.info("No meaningful dialogue episodes produced from export.")
            return ImportSummary(
                chat_id=parsed.chat_id,
                chat_title=parsed.chat_title,
                total_raw_messages=total_raw,
                meaningful_messages=len(meaningful_messages),
                dropped_noise_messages=dropped_count,
                members_synced=members_synced,
                total_episodes=0,
                processed_episodes=0,
                skipped_episodes=0,
                dry_run=dry_run,
                completed=True,
            )

        # 5. Checkpoint handling
        checkpoint_path = self.get_checkpoint_path(parsed.chat_id)
        checkpoint: ImportCheckpoint | None = None

        if resume:
            checkpoint = ImportCheckpoint.load(checkpoint_path)
            if checkpoint:
                logger.info(
                    "Resuming import from checkpoint",
                    checkpoint_file=str(checkpoint_path),
                    already_processed=len(checkpoint.processed_indices),
                    total_recorded=checkpoint.total_episodes,
                )

        if checkpoint is None:
            checkpoint = ImportCheckpoint(
                chat_id=parsed.chat_id,
                chat_title=parsed.chat_title,
                export_file=str(resolved_file),
                total_episodes=len(episodes),
            )
            if not dry_run:
                checkpoint.save(checkpoint_path)

        already_done_set = set(checkpoint.processed_indices)
        episodes_to_run = [ep for ep in episodes if ep.episode_index not in already_done_set]
        skipped_count = len(episodes) - len(episodes_to_run)

        logger.info(
            "Episode ingestion plan",
            total_episodes=len(episodes),
            skipped_previously=skipped_count,
            episodes_to_process=len(episodes_to_run),
            delay_seconds=delay,
        )

        # 6. Ingestion loop
        processed_this_run = 0
        for ep in episodes_to_run:
            if dry_run:
                logger.info(
                    "Dry-run: Would ingest episode",
                    index=ep.episode_index,
                    messages_count=len(ep.messages),
                    source_user=ep.source_user_name,
                    reference_time=ep.reference_time.isoformat(),
                )
                processed_this_run += 1
                checkpoint.mark_episode_done(ep.episode_index)
            else:
                if self.memory_backend is None:
                    raise RuntimeError("Memory backend not configured for non-dry-run import.")

                logger.debug(
                    "Ingesting episode into memory backend",
                    index=ep.episode_index,
                    messages_count=len(ep.messages),
                )
                await self.memory_backend.ingest_episode(
                    text=ep.text,
                    group_id=str(ep.chat_id),
                    source_user_name=ep.source_user_name,
                    reference_time=ep.reference_time,
                )

                checkpoint.mark_episode_done(ep.episode_index)
                checkpoint.save(checkpoint_path)
                processed_this_run += 1

                if delay > 0:
                    await asyncio.sleep(delay)

        if not dry_run and checkpoint.completed:
            checkpoint.save(checkpoint_path)

        logger.info(
            "Chat import finished",
            chat_id=parsed.chat_id,
            episodes_processed=processed_this_run,
            total_episodes=len(episodes),
            dry_run=dry_run,
        )

        return ImportSummary(
            chat_id=parsed.chat_id,
            chat_title=parsed.chat_title,
            total_raw_messages=total_raw,
            meaningful_messages=len(meaningful_messages),
            dropped_noise_messages=dropped_count,
            members_synced=members_synced,
            total_episodes=len(episodes),
            processed_episodes=processed_this_run,
            skipped_episodes=skipped_count,
            dry_run=dry_run,
            completed=checkpoint.completed or dry_run,
        )
