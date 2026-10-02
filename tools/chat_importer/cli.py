"""Command-line interface for Telegram Desktop chat history importer."""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Sequence
from pathlib import Path

from bot.config import Settings
from bot.db.engine import create_async_engine_instance, create_session_factory
from bot.db.graphiti import GraphitiMemoryBackend
from bot.db.repository import MemberRepository
from bot.log import get_logger, setup_logging
from bot.services.message_filter import MessageNoiseFilter
from tools.chat_importer.chunker import ConversationChunker
from tools.chat_importer.parser import TelegramExportParser
from tools.chat_importer.pipeline import ImportPipeline, ImportSummary

logger = get_logger(__name__)


def build_parser() -> argparse.ArgumentParser:
    """Construct CLI argument parser for chat importer."""
    parser = argparse.ArgumentParser(
        prog="tg-import",
        description="Import Telegram Desktop chat export JSON into PostgreSQL and Graphiti memory.",
    )

    parser.add_argument(
        "--file",
        "-f",
        required=True,
        type=Path,
        help="Path to Telegram Desktop JSON export file (result.json).",
    )

    parser.add_argument(
        "--chat-id",
        "-c",
        type=int,
        default=None,
        help="Target Telegram chat ID (defaults to settings.group_chat_id or auto-prefixed export ID).",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate import process without modifying database or knowledge graph.",
    )

    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume an interrupted import from saved state checkpoint (.import_state_<chat_id>.json).",
    )

    parser.add_argument(
        "--gap-minutes",
        type=int,
        default=20,
        help="Idle time gap in minutes to segment dialogue episodes (default: 20).",
    )

    parser.add_argument(
        "--max-messages",
        type=int,
        default=15,
        help="Maximum messages allowed in a single dialogue episode (default: 15).",
    )

    parser.add_argument(
        "--delay",
        type=float,
        default=0.0,
        help="Delay in seconds between episode ingestions to respect API rate limits (default: 0.0).",
    )

    parser.add_argument(
        "--no-db",
        action="store_true",
        help="Skip PostgreSQL database synchronization for chat and member records.",
    )

    parser.add_argument(
        "--min-length",
        type=int,
        default=None,
        help="Minimum message text length threshold to pass noise filter.",
    )

    return parser


def print_summary(summary: ImportSummary) -> None:
    """Print readable text summary of import results."""
    mode_str = "DRY RUN (NO CHANGES)" if summary.dry_run else "LIVE INGESTION"
    status_str = "Completed" if summary.completed else "Interrupted / Partial"
    banner = "=" * 60
    lines = [
        "",
        banner,
        f" Chat Import Summary: {summary.chat_title} ({summary.chat_id})",
        banner,
        f" Mode:                   {mode_str}",
        f" Total Raw Messages:     {summary.total_raw_messages}",
        f" Meaningful Messages:    {summary.meaningful_messages}",
        f" Dropped Noise Messages: {summary.dropped_noise_messages}",
        f" DB Members Synced:      {summary.members_synced}",
        f" Total Episodes:         {summary.total_episodes}",
        f" Episodes Processed:     {summary.processed_episodes}",
        f" Episodes Skipped:       {summary.skipped_episodes}",
        f" Final Status:           {status_str}",
        banner,
        "",
    ]
    print("\n".join(lines))


async def async_main(argv: Sequence[str] | None = None) -> int:
    """Async entrypoint for CLI runner."""
    parser = build_parser()
    args = parser.parse_args(argv)

    settings = Settings()
    setup_logging(debug=settings.debug)

    engine = None
    member_repo = None
    memory_backend = None

    try:
        # Initialize PostgreSQL if DB sync requested
        if not args.no_db and not args.dry_run:
            try:
                engine = create_async_engine_instance(settings.postgres_dsn)
                session_factory = create_session_factory(engine)
                member_repo = MemberRepository(session_factory)
            except Exception as exc:
                logger.error("Failed to initialize database connection pool", error=str(exc))
                return 1

        # Initialize Graphiti memory backend if not dry-run
        if not args.dry_run:
            try:
                memory_backend = GraphitiMemoryBackend(
                    neo4j_uri=settings.neo4j_uri,
                    neo4j_user=settings.neo4j_user,
                    neo4j_password=settings.neo4j_password,
                    openai_api_key=settings.openai_api_key,
                    extraction_model=settings.openai_extraction_model,
                    embedding_model=settings.openai_embedding_model,
                )
            except Exception as exc:
                logger.error("Failed to initialize Graphiti memory backend", error=str(exc))
                return 1

        noise_filter = MessageNoiseFilter()
        if args.min_length is not None:
            noise_filter.min_length = args.min_length

        chunker = ConversationChunker(
            gap_minutes=args.gap_minutes,
            max_messages=args.max_messages,
        )

        pipeline = ImportPipeline(
            parser=TelegramExportParser(),
            noise_filter=noise_filter,
            chunker=chunker,
            member_repo=member_repo,
            memory_backend=memory_backend,
            settings=settings,
        )

        summary = await pipeline.run(
            file_path=args.file,
            chat_id=args.chat_id,
            dry_run=args.dry_run,
            resume=args.resume,
            gap_minutes=args.gap_minutes,
            max_messages=args.max_messages,
            delay=args.delay,
            no_db=args.no_db,
            min_length=args.min_length,
        )

        print_summary(summary)
        return 0

    except Exception as exc:
        logger.exception("Import failed with unhandled error", error=str(exc))
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    finally:
        if memory_backend is not None:
            try:
                await memory_backend.close()
            except Exception as exc:
                logger.warning("Error closing memory backend", error=str(exc))
        if engine is not None:
            try:
                await engine.dispose()
            except Exception as exc:
                logger.warning("Error disposing engine", error=str(exc))


def main(argv: Sequence[str] | None = None) -> int:
    """Synchronous entrypoint."""
    return asyncio.run(async_main(argv))


if __name__ == "__main__":
    sys.exit(main())
