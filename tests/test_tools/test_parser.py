"""Unit tests for Telegram Desktop export parser."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from tools.chat_importer.parser import (
    TelegramExportParser,
    extract_text_content,
    parse_export,
    parse_member_identity,
    parse_timestamp,
    parse_user_id,
    resolve_chat_id,
)


def test_resolve_chat_id_cli_priority() -> None:
    """CLI chat ID should take highest priority."""
    chat_id = resolve_chat_id(cli_chat_id=-100999999, settings_chat_id=-100888888, export_id=777777)
    assert chat_id == -100999999


def test_resolve_chat_id_settings_fallback() -> None:
    """Settings chat ID should be used if CLI argument is not provided."""
    chat_id = resolve_chat_id(cli_chat_id=None, settings_chat_id=-100888888, export_id=777777)
    assert chat_id == -100888888


def test_resolve_chat_id_export_prefix_positive() -> None:
    """Positive export ID should be auto-prefixed with -100."""
    chat_id = resolve_chat_id(cli_chat_id=None, settings_chat_id=0, export_id=123456789)
    assert chat_id == -100123456789


def test_resolve_chat_id_export_prefix_starting_with_100() -> None:
    """Positive export ID already starting with 100 should be negated properly."""
    chat_id = resolve_chat_id(cli_chat_id=None, settings_chat_id=None, export_id=100123456789)
    assert chat_id == -100123456789


def test_resolve_chat_id_export_already_negative() -> None:
    """Negative export ID should remain unchanged."""
    chat_id = resolve_chat_id(cli_chat_id=None, settings_chat_id=None, export_id=-100123456789)
    assert chat_id == -100123456789


def test_resolve_chat_id_unresolved_raises() -> None:
    """Missing all chat ID sources must raise ValueError."""
    with pytest.raises(ValueError, match="Chat ID could not be determined"):
        resolve_chat_id(cli_chat_id=None, settings_chat_id=None, export_id=None)


def test_extract_text_content_string() -> None:
    """Plain string text should be stripped and returned."""
    assert extract_text_content("  Hello world!  ") == "Hello world!"


def test_extract_text_content_list_mixed() -> None:
    """List with mixed strings and entity dicts should be concatenated."""
    raw = [
        "Welcome to ",
        {"type": "link", "text": "https://example.com"},
        ", where we study ",
        {"type": "bold", "text": "Python"},
        "!",
    ]
    assert extract_text_content(raw) == "Welcome to https://example.com, where we study Python!"


def test_extract_text_content_fallback_entities() -> None:
    """When raw text is empty, fall back to text_entities list."""
    entities = [
        {"type": "plain", "text": "Message from entities"},
    ]
    assert extract_text_content("", text_entities=entities) == "Message from entities"


def test_parse_user_id() -> None:
    """User IDs with different string prefixes and types should parse correctly."""
    assert parse_user_id("user12345678") == 12345678
    assert parse_user_id("channel87654321") == 87654321
    assert parse_user_id(999888) == 999888
    assert parse_user_id("user-100555") == -100555
    assert parse_user_id(None) == 0
    assert parse_user_id("invalid") == 0


def test_parse_timestamp_unixtime() -> None:
    """Unix epoch timestamp string or int should parse to UTC datetime."""
    msg = {"date_unixtime": "1704067200"}
    dt = parse_timestamp(msg)
    assert dt == datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)


def test_parse_timestamp_iso() -> None:
    """ISO format date string should parse to UTC datetime."""
    msg = {"date": "2024-05-10T15:30:00"}
    dt = parse_timestamp(msg)
    assert dt == datetime(2024, 5, 10, 15, 30, 0, tzinfo=UTC)


def test_parse_member_identity() -> None:
    """Display name should split into first and last name and preserve display_name."""
    member = parse_member_identity(12345, "Alex Turner")
    assert member is not None
    assert member.telegram_user_id == 12345
    assert member.first_name == "Alex"
    assert member.last_name == "Turner"
    assert member.display_name == "Alex Turner"

    single_name_member = parse_member_identity(67890, "Alice")
    assert single_name_member is not None
    assert single_name_member.first_name == "Alice"
    assert single_name_member.last_name is None
    assert single_name_member.display_name == "Alice"

    assert parse_member_identity(0, "Nobody") is None


def test_parse_dict_messages() -> None:
    """Parser should ignore service messages and extract messages and unique members."""
    data = {
        "name": "Research Group",
        "id": 555666,
        "messages": [
            {
                "id": 1,
                "type": "service",
                "action": "joined_group",
                "date": "2024-01-01T12:00:00",
                "from": "Bob",
                "from_id": "user100",
            },
            {
                "id": 2,
                "type": "message",
                "date": "2024-01-01T12:01:00",
                "from": "Bob Dylan",
                "from_id": "user100",
                "text": "Hello team, let's start the project.",
            },
            {
                "id": 3,
                "type": "message",
                "date": "2024-01-01T12:02:00",
                "from": "Alice Cooper",
                "from_id": "user200",
                "reply_to_message_id": 2,
                "text": "Sounds good! I will work on the backend.",
            },
            {
                "id": 4,
                "type": "message",
                "date": "2024-01-01T12:03:00",
                "from": "Bob Dylan",
                "from_id": "user100",
                "text": "",  # Empty text message, e.g. photo without caption
            },
        ],
    }

    parser = TelegramExportParser()
    parsed = parser.parse_dict(data)

    assert parsed.chat_id == -100555666
    assert parsed.chat_title == "Research Group"
    assert len(parsed.messages) == 2
    assert parsed.messages[0].message_id == 2
    assert parsed.messages[0].user_id == 100
    assert parsed.messages[0].display_name == "Bob Dylan"
    assert parsed.messages[0].text == "Hello team, let's start the project."

    assert parsed.messages[1].message_id == 3
    assert parsed.messages[1].reply_to_message_id == 2

    # Verify unique members
    assert len(parsed.members) == 2
    user_ids = {m.telegram_user_id for m in parsed.members}
    assert user_ids == {100, 200}


def test_parse_file(tmp_path: Path) -> None:
    """Parser should load and parse JSON export from disk."""
    export_file = tmp_path / "result.json"
    data = {
        "name": "Local Test Chat",
        "id": 111222,
        "messages": [
            {
                "id": 10,
                "type": "message",
                "date": "2024-02-01T10:00:00",
                "from": "Charlie",
                "from_id": "user300",
                "text": "First message from disk.",
            }
        ],
    }
    export_file.write_text(json.dumps(data), encoding="utf-8")

    parsed = parse_export(export_file, chat_id=-100999)
    assert parsed.chat_id == -100999
    assert parsed.chat_title == "Local Test Chat"
    assert len(parsed.messages) == 1
    assert parsed.messages[0].text == "First message from disk."


def test_parse_file_errors(tmp_path: Path) -> None:
    """Parser should raise appropriate errors for missing or invalid files."""
    parser = TelegramExportParser()
    with pytest.raises(FileNotFoundError):
        parser.parse_file(tmp_path / "nonexistent.json")

    invalid_file = tmp_path / "invalid.json"
    invalid_file.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="root JSON element must be an object"):
        parser.parse_file(invalid_file)
