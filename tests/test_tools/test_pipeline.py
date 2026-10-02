"""Unit tests for ImportPipeline and ImportCheckpoint."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.db.repository import MemberRepository
from bot.models import MemoryBackend
from tools.chat_importer.pipeline import ImportCheckpoint, ImportPipeline


@pytest.fixture
def sample_export_file(tmp_path: Path) -> Path:
    """Create a sample Telegram export JSON file for pipeline testing."""
    file_path = tmp_path / "result.json"
    data = {
        "name": "Dev Chat",
        "id": 1009876543,
        "messages": [
            {
                "id": 1,
                "type": "message",
                "date": "2024-03-01T10:00:00",
                "from": "Alice Walker",
                "from_id": "user101",
                "text": "Hello everyone, starting the morning standup.",
            },
            {
                "id": 2,
                "type": "message",
                "date": "2024-03-01T10:01:00",
                "from": "Bob Dylan",
                "from_id": "user102",
                "text": "/help",  # Noise: command
            },
            {
                "id": 3,
                "type": "message",
                "date": "2024-03-01T10:02:00",
                "from": "Bob Dylan",
                "from_id": "user102",
                "text": "I am working on the Graphiti integration today.",
            },
            {
                "id": 4,
                "type": "message",
                "date": "2024-03-01T10:35:00",  # Idle gap > 20 mins -> splits to episode 2
                "from": "Alice Walker",
                "from_id": "user101",
                "text": "Great, let us review the PR this afternoon.",
            },
        ],
    }
    file_path.write_text(json.dumps(data), encoding="utf-8")
    return file_path


def test_checkpoint_save_and_load(tmp_path: Path) -> None:
    """ImportCheckpoint should serialize and deserialize accurately."""
    state_file = tmp_path / ".import_state_-1001009876543.json"
    cp = ImportCheckpoint(
        chat_id=-1001009876543,
        chat_title="Dev Chat",
        export_file="result.json",
        total_episodes=5,
    )
    cp.mark_episode_done(0)
    cp.mark_episode_done(1)
    cp.save(state_file)

    loaded = ImportCheckpoint.load(state_file)
    assert loaded is not None
    assert loaded.chat_id == -1001009876543
    assert loaded.chat_title == "Dev Chat"
    assert loaded.total_episodes == 5
    assert loaded.processed_indices == [0, 1]
    assert loaded.last_processed_index == 1
    assert loaded.completed is False


@pytest.mark.asyncio
async def test_pipeline_dry_run(sample_export_file: Path, tmp_path: Path) -> None:
    """In dry-run mode, neither DB upsert nor memory ingestion should be called."""
    mock_member_repo = MagicMock(spec=MemberRepository)
    mock_member_repo.upsert_member = AsyncMock()

    mock_memory = MagicMock(spec=MemoryBackend)
    mock_memory.ingest_episode = AsyncMock()

    pipeline = ImportPipeline(
        member_repo=mock_member_repo,
        memory_backend=mock_memory,
        state_dir=tmp_path,
    )

    summary = await pipeline.run(
        file_path=sample_export_file,
        dry_run=True,
    )

    assert summary.dry_run is True
    assert summary.total_raw_messages == 4
    # 1 command dropped (/help), 3 meaningful messages kept
    assert summary.meaningful_messages == 3
    assert summary.dropped_noise_messages == 1
    assert summary.total_episodes == 2
    assert summary.processed_episodes == 2

    # Verify no external mutations occurred
    mock_member_repo.upsert_member.assert_not_called()
    mock_memory.ingest_episode.assert_not_called()


@pytest.mark.asyncio
async def test_pipeline_no_db(sample_export_file: Path, tmp_path: Path) -> None:
    """When --no-db is active, database member upsert should be skipped."""
    mock_member_repo = MagicMock(spec=MemberRepository)
    mock_member_repo.upsert_member = AsyncMock()

    mock_memory = MagicMock(spec=MemoryBackend)
    mock_memory.ingest_episode = AsyncMock()

    pipeline = ImportPipeline(
        member_repo=mock_member_repo,
        memory_backend=mock_memory,
        state_dir=tmp_path,
    )

    summary = await pipeline.run(
        file_path=sample_export_file,
        no_db=True,
    )

    assert summary.members_synced == 0
    mock_member_repo.upsert_member.assert_not_called()
    assert mock_memory.ingest_episode.call_count == 2


@pytest.mark.asyncio
async def test_pipeline_full_execution(sample_export_file: Path, tmp_path: Path) -> None:
    """Full execution should upsert members and ingest all episodes into Graphiti."""
    mock_member_repo = MagicMock(spec=MemberRepository)
    mock_member_repo.upsert_member = AsyncMock()

    mock_memory = MagicMock(spec=MemoryBackend)
    mock_memory.ingest_episode = AsyncMock()

    pipeline = ImportPipeline(
        member_repo=mock_member_repo,
        memory_backend=mock_memory,
        state_dir=tmp_path,
    )

    summary = await pipeline.run(
        file_path=sample_export_file,
        chat_id=-100999,
        gap_minutes=20,
        max_messages=15,
    )

    assert summary.chat_id == -100999
    assert summary.total_episodes == 2
    assert summary.processed_episodes == 2
    assert summary.skipped_episodes == 0
    assert summary.completed is True

    # Check member DB sync
    assert mock_member_repo.upsert_member.call_count == 2
    # Check Graphiti ingestion
    assert mock_memory.ingest_episode.call_count == 2

    # First call: Episode 0 (Alice and Bob)
    call0 = mock_memory.ingest_episode.call_args_list[0]
    assert "Alice Walker: Hello everyone" in call0.kwargs["text"]
    assert "Bob Dylan: I am working on the Graphiti integration today." in call0.kwargs["text"]
    assert call0.kwargs["group_id"] == "-100999"

    # Second call: Episode 1 (Alice Walker after 35 mins)
    call1 = mock_memory.ingest_episode.call_args_list[1]
    assert "Alice Walker: Great, let us review" in call1.kwargs["text"]

    # Checkpoint should exist and be completed
    cp_path = pipeline.get_checkpoint_path(-100999)
    assert cp_path.is_file()
    loaded_cp = ImportCheckpoint.load(cp_path)
    assert loaded_cp is not None
    assert loaded_cp.completed is True
    assert loaded_cp.processed_indices == [0, 1]


@pytest.mark.asyncio
async def test_pipeline_resume(sample_export_file: Path, tmp_path: Path) -> None:
    """Resume mode should skip previously completed episodes."""
    mock_member_repo = MagicMock(spec=MemberRepository)
    mock_member_repo.upsert_member = AsyncMock()

    mock_memory = MagicMock(spec=MemoryBackend)
    mock_memory.ingest_episode = AsyncMock()

    pipeline = ImportPipeline(
        member_repo=mock_member_repo,
        memory_backend=mock_memory,
        state_dir=tmp_path,
    )

    # Pre-populate state checkpoint with episode 0 already done
    cp_path = pipeline.get_checkpoint_path(-1009876543)
    existing_cp = ImportCheckpoint(
        chat_id=-1009876543,
        chat_title="Dev Chat",
        export_file=str(sample_export_file),
        total_episodes=2,
        processed_indices=[0],
        last_processed_index=0,
    )
    existing_cp.save(cp_path)

    summary = await pipeline.run(
        file_path=sample_export_file,
        chat_id=-1009876543,
        resume=True,
    )

    assert summary.total_episodes == 2
    assert summary.skipped_episodes == 1
    assert summary.processed_episodes == 1
    assert summary.completed is True

    # Memory ingestion called only for episode 1
    assert mock_memory.ingest_episode.call_count == 1
    call = mock_memory.ingest_episode.call_args
    assert "review the PR" in call.kwargs["text"]


@pytest.mark.asyncio
async def test_pipeline_delay_applied(sample_export_file: Path, tmp_path: Path) -> None:
    """Delay parameter should cause asyncio.sleep between episode ingestions."""
    mock_memory = MagicMock(spec=MemoryBackend)
    mock_memory.ingest_episode = AsyncMock()

    pipeline = ImportPipeline(
        memory_backend=mock_memory,
        state_dir=tmp_path,
    )

    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        await pipeline.run(
            file_path=sample_export_file,
            no_db=True,
            delay=1.5,
        )

        assert mock_sleep.call_count == 2
        mock_sleep.assert_called_with(1.5)


@pytest.mark.asyncio
async def test_pipeline_empty_export(tmp_path: Path) -> None:
    """Export with no messages should produce clean zero-episode summary."""
    empty_file = tmp_path / "empty.json"
    empty_file.write_text(
        json.dumps({"name": "Empty Chat", "id": 12345, "messages": []}), encoding="utf-8"
    )

    pipeline = ImportPipeline(state_dir=tmp_path)
    summary = await pipeline.run(file_path=empty_file, no_db=True, dry_run=True)

    assert summary.total_raw_messages == 0
    assert summary.total_episodes == 0
    assert summary.processed_episodes == 0
    assert summary.completed is True
