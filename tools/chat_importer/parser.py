"""Telegram Desktop JSON export parser.

Parses machine-readable chat export files from Telegram Desktop into domain
ChatMessage and MemberIdentity objects ready for pipeline ingestion.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from bot.log import get_logger
from bot.models import ChatMessage, MemberIdentity
from tools.chat_importer.contracts import (
    TelegramChatExportContract,
)

logger = get_logger(__name__)


def resolve_chat_id(
    cli_chat_id: int | None = None,
    settings_chat_id: int | None = None,
    export_id: int | None = None,
) -> int:
    """Resolve target Telegram chat ID using precedence hierarchy.

    Precedence:
    1. Explicit CLI argument (--chat-id).
    2. Settings default (settings.group_chat_id).
    3. Auto-prefixed export ID from JSON (e.g. positive 123456 -> -100123456).

    Raises:
        ValueError: If no valid chat ID can be determined.
    """
    if cli_chat_id is not None and cli_chat_id != 0:
        return cli_chat_id

    if settings_chat_id is not None and settings_chat_id != 0:
        return settings_chat_id

    if export_id is not None and export_id != 0:
        if export_id < 0:
            return export_id
        str_id = str(export_id)
        if str_id.startswith("100"):
            return -int(str_id)
        return -int(f"100{str_id}")

    raise ValueError("Chat ID could not be determined from CLI, settings, or export file.")


def extract_text_content(
    raw_text: Any,
    text_entities: list[dict[str, Any]] | None = None,
) -> str:
    """Extract plain string message content from heterogeneous Telegram export formats."""
    text_parts: list[str] = []

    if isinstance(raw_text, str):
        text_parts.append(raw_text)
    elif isinstance(raw_text, list):
        for item in raw_text:
            if isinstance(item, str):
                text_parts.append(item)
            elif isinstance(item, dict):
                text_parts.append(str(item.get("text", "")))
            else:
                text_parts.append(str(item))

    joined_text = "".join(text_parts).strip()

    # Fallback to text_entities if main text field was empty or whitespace
    if not joined_text and text_entities:
        entity_parts: list[str] = []
        for ent in text_entities:
            if isinstance(ent, dict):
                entity_parts.append(str(ent.get("text", "")))
            elif isinstance(ent, str):
                entity_parts.append(ent)
        joined_text = "".join(entity_parts).strip()

    return joined_text


def parse_user_id(from_id: Any) -> int:
    """Parse user ID from raw Telegram Desktop representation."""
    if from_id is None:
        return 0
    if isinstance(from_id, int):
        return from_id

    val = str(from_id).strip()
    if val.startswith("user"):
        val = val[4:]
    elif val.startswith("channel"):
        val = val[7:]

    matches = re.findall(r"-?\d+", val)
    if matches:
        return int(matches[0])
    return 0


def parse_timestamp(msg: dict[str, Any]) -> datetime:
    """Extract UTC timestamp from message record."""
    date_unixtime = msg.get("date_unixtime")
    if date_unixtime is not None:
        try:
            return datetime.fromtimestamp(int(date_unixtime), tz=UTC)
        except (ValueError, TypeError):
            pass

    date_str = msg.get("date")
    if isinstance(date_str, str) and date_str.strip():
        try:
            dt = datetime.fromisoformat(date_str.strip())
            if dt.tzinfo is None:
                return dt.replace(tzinfo=UTC)
            return dt.astimezone(UTC)
        except ValueError:
            pass

    return datetime.now(UTC)


def parse_member_identity(user_id: int, from_name: str | None) -> MemberIdentity | None:
    """Construct MemberIdentity object from user ID and display name."""
    if user_id == 0:
        return None

    first_name: str | None = None
    last_name: str | None = None

    if from_name:
        parts = from_name.strip().split(" ", 1)
        first_name = parts[0]
        if len(parts) > 1 and parts[1].strip():
            last_name = parts[1].strip()

    return MemberIdentity(
        telegram_user_id=user_id,
        username=None,
        first_name=first_name,
        last_name=last_name,
    )


@dataclass(frozen=True, slots=True)
class ParsedChatExport:
    """Structured representation of parsed Telegram Desktop chat export."""

    chat_id: int
    chat_title: str
    messages: list[ChatMessage]
    members: list[MemberIdentity]


class TelegramExportParser:
    """Parser for Telegram Desktop chat export JSON files."""

    def parse_dict(
        self,
        data: dict[str, Any],
        chat_id: int | None = None,
        fallback_chat_id: int | None = None,
    ) -> ParsedChatExport:
        """Parse raw JSON dict into domain objects."""
        export_contract = TelegramChatExportContract.model_validate(data)
        chat_title = export_contract.name
        raw_export_id = export_contract.id

        export_id: int | None = None
        if isinstance(raw_export_id, int):
            export_id = raw_export_id
        elif isinstance(raw_export_id, str):
            clean_str = raw_export_id.strip()
            if clean_str.lstrip("-").isdigit():
                export_id = int(clean_str)

        final_chat_id = resolve_chat_id(
            cli_chat_id=chat_id,
            settings_chat_id=fallback_chat_id,
            export_id=export_id,
        )

        parsed_messages: list[ChatMessage] = []
        members_map: dict[int, MemberIdentity] = {}

        for msg in export_contract.messages:
            # Ignore service messages (join/leave, pinned messages, call events, etc.)
            if msg.type == "service":
                continue

            text = msg.get_clean_text()
            if not text:
                continue

            user_id = msg.get_user_id()
            from_name = msg.from_name
            display_name = (
                str(from_name).strip()
                if from_name
                else (f"User {user_id}" if user_id else "Anonymous")
            )
            timestamp = msg.get_timestamp()
            message_id = msg.id
            reply_to_id = msg.reply_to_message_id

            chat_msg = ChatMessage(
                chat_id=final_chat_id,
                user_id=user_id,
                text=text,
                timestamp=timestamp,
                message_id=message_id,
                display_name=display_name,
                reply_to_message_id=reply_to_id,
            )
            parsed_messages.append(chat_msg)

            if user_id != 0 and user_id not in members_map:
                member = parse_member_identity(user_id, str(from_name) if from_name else None)
                if member is not None:
                    members_map[user_id] = member

        logger.info(
            "Parsed chat export",
            chat_id=final_chat_id,
            chat_title=chat_title,
            messages_count=len(parsed_messages),
            members_count=len(members_map),
        )

        return ParsedChatExport(
            chat_id=final_chat_id,
            chat_title=chat_title,
            messages=parsed_messages,
            members=list(members_map.values()),
        )

    def parse_file(
        self,
        file_path: str | Path,
        chat_id: int | None = None,
        fallback_chat_id: int | None = None,
    ) -> ParsedChatExport:
        """Read and parse Telegram Desktop export file."""
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"Export file not found: {file_path}")

        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            raise ValueError(
                f"Invalid export file: root JSON element must be an object in {file_path}"
            )

        return self.parse_dict(data, chat_id=chat_id, fallback_chat_id=fallback_chat_id)


def parse_export(
    source: str | Path | dict[str, Any],
    chat_id: int | None = None,
    fallback_chat_id: int | None = None,
) -> ParsedChatExport:
    """Convenience functional interface for Telegram export parsing."""
    parser = TelegramExportParser()
    if isinstance(source, dict):
        return parser.parse_dict(source, chat_id=chat_id, fallback_chat_id=fallback_chat_id)
    return parser.parse_file(source, chat_id=chat_id, fallback_chat_id=fallback_chat_id)
