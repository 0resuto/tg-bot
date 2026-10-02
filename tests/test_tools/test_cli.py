"""Unit tests for chat importer CLI entrypoint."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from tools.chat_importer.cli import async_main, build_parser, main


def test_build_parser_arguments() -> None:
    """Verify all required flags and defaults are defined on the CLI parser."""
    parser = build_parser()

    args = parser.parse_args(
        [
            "--file",
            "export.json",
            "--chat-id",
            "-100123456",
            "--dry-run",
            "--resume",
            "--gap-minutes",
            "30",
            "--max-messages",
            "25",
            "--delay",
            "1.5",
            "--no-db",
            "--min-length",
            "10",
        ]
    )

    assert args.file == Path("export.json")
    assert args.chat_id == -100123456
    assert args.dry_run is True
    assert args.resume is True
    assert args.gap_minutes == 30
    assert args.max_messages == 25
    assert args.delay == 1.5
    assert args.no_db is True
    assert args.min_length == 10


def test_build_parser_defaults() -> None:
    """Verify standard default options."""
    parser = build_parser()
    args = parser.parse_args(["--file", "export.json"])

    assert args.chat_id is None
    assert args.dry_run is False
    assert args.resume is False
    assert args.gap_minutes == 20
    assert args.max_messages == 15
    assert args.delay == 0.0
    assert args.no_db is False
    assert args.min_length is None


def test_build_parser_missing_required_file() -> None:
    """Parser should error when --file is missing."""
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args([])


@pytest.mark.asyncio
async def test_cli_dry_run_execution(tmp_path: Path) -> None:
    """CLI execution in dry-run and no-db mode should execute cleanly and return 0."""
    export_file = tmp_path / "result.json"
    data = {
        "name": "CLI Test Chat",
        "id": 999888,
        "messages": [
            {
                "id": 1,
                "type": "message",
                "date": "2024-01-01T12:00:00",
                "from": "Tester",
                "from_id": "user1",
                "text": "CLI dry run testing message.",
            }
        ],
    }
    export_file.write_text(json.dumps(data), encoding="utf-8")

    exit_code = await async_main(
        [
            "--file",
            str(export_file),
            "--dry-run",
            "--no-db",
        ]
    )
    assert exit_code == 0


@pytest.mark.asyncio
async def test_cli_missing_file_error() -> None:
    """CLI execution with nonexistent file should handle error and return 1."""
    exit_code = await async_main(
        [
            "--file",
            "nonexistent_file_path_12345.json",
            "--dry-run",
            "--no-db",
        ]
    )
    assert exit_code == 1


def test_sync_main_wrapper(tmp_path: Path) -> None:
    """Synchronous main() should forward to async_main."""
    export_file = tmp_path / "result.json"
    data = {"name": "Test", "id": 1, "messages": []}
    export_file.write_text(json.dumps(data), encoding="utf-8")

    with patch("tools.chat_importer.cli.async_main", new_callable=AsyncMock) as mock_async_main:
        mock_async_main.return_value = 0
        code = main(["--file", str(export_file), "--dry-run", "--no-db"])
        assert code == 0
        mock_async_main.assert_called_once()
