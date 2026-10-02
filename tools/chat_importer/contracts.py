"""Contract-Driven Development (CDD) schemas and runtime validation models.

Defines strict type contracts, validation constraints, and serialization schemas
for Telegram Desktop exports, dialogue episodes, and state checkpoints.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from bot.models import ChatMessage


class TelegramTextEntityContract(BaseModel):
    """Contract for formatted text entities within Telegram messages."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    type: str = Field(default="plain", description="Entity type: bold, italic, link, mention, etc.")
    text: str = Field(default="", description="Text content of the entity fragment")


class TelegramMessageContract(BaseModel):
    """Runtime-validated contract for a raw message in Telegram Desktop export."""

    model_config = ConfigDict(extra="ignore", frozen=True, populate_by_name=True)

    id: int = Field(..., description="Unique message ID")
    type: str = Field(default="message", description="Message type: message, service")
    date: str | None = Field(default=None, description="ISO timestamp string")
    date_unixtime: str | int | None = Field(default=None, description="Unix timestamp")
    from_name: str | None = Field(default=None, alias="from", description="Sender display name")
    from_id: str | int | None = Field(
        default=None, description="Raw sender identifier (e.g. user123, channel456)"
    )
    text: str | list[str | dict[str, Any]] = Field(
        default="", description="Message text or rich entity array"
    )
    text_entities: list[TelegramTextEntityContract] = Field(
        default_factory=list, description="Nested text entities"
    )
    reply_to_message_id: int | None = Field(default=None, description="Reply target message ID")
    action: str | None = Field(default=None, description="Service action name if service message")

    @field_validator("id", mode="before")
    @classmethod
    def _validate_id(cls, v: Any) -> int:
        if isinstance(v, int):
            return v
        try:
            return int(v)
        except (ValueError, TypeError) as exc:
            raise ValueError(f"Invalid message id: {v}") from exc

    def get_clean_text(self) -> str:
        """Extract sanitized plain string content from heterogeneous text payload."""
        text_parts: list[str] = []

        if isinstance(self.text, str):
            text_parts.append(self.text)
        elif isinstance(self.text, list):
            for item in self.text:
                if isinstance(item, str):
                    text_parts.append(item)
                elif isinstance(item, dict):
                    text_parts.append(str(item.get("text", "")))
                else:
                    text_parts.append(str(item))

        joined = "".join(text_parts).strip()
        if not joined and self.text_entities:
            entity_parts = [ent.text for ent in self.text_entities if ent.text]
            joined = "".join(entity_parts).strip()

        return joined

    def get_user_id(self) -> int:
        """Parse numerical user ID from raw from_id representation."""
        if self.from_id is None:
            return 0
        if isinstance(self.from_id, int):
            return self.from_id

        val = str(self.from_id).strip()
        if val.startswith("user"):
            val = val[4:]
        elif val.startswith("channel"):
            val = val[7:]

        matches = re.findall(r"-?\d+", val)
        if matches:
            return int(matches[0])
        return 0

    def get_timestamp(self) -> datetime:
        """Parse and normalize timestamp to timezone-aware UTC datetime."""
        if self.date_unixtime is not None:
            try:
                return datetime.fromtimestamp(int(self.date_unixtime), tz=UTC)
            except (ValueError, TypeError):
                pass

        if self.date and isinstance(self.date, str) and self.date.strip():
            try:
                dt = datetime.fromisoformat(self.date.strip())
                if dt.tzinfo is None:
                    return dt.replace(tzinfo=UTC)
                return dt.astimezone(UTC)
            except ValueError:
                pass

        return datetime.now(UTC)


class TelegramChatExportContract(BaseModel):
    """Contract validating the root structure of a Telegram Desktop JSON export."""

    model_config = ConfigDict(extra="ignore")

    id: int | str | None = Field(default=None, description="Chat identifier from export")
    name: str = Field(default="Imported Chat", description="Title or name of the chat")
    type: str = Field(default="public_supergroup", description="Chat type")
    messages: list[TelegramMessageContract] = Field(
        default_factory=list, description="List of exported messages"
    )

    @field_validator("name", mode="before")
    @classmethod
    def _clean_name(cls, v: Any) -> str:
        if v is None:
            return "Imported Chat"
        clean = str(v).strip()
        return clean if clean else "Imported Chat"


class DialogueEpisodeContract(BaseModel):
    """Runtime contract for a segmented dialogue episode prepared for Graphiti."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    episode_index: int = Field(ge=0, description="Sequential episode index starting from 0")
    chat_id: int = Field(..., description="Target chat ID (must not be 0)")
    messages: list[ChatMessage] = Field(min_length=1, description="Messages comprising the episode")
    text: str = Field(min_length=1, description="Formatted dialogue text with speaker prefixes")
    source_user_name: str = Field(
        min_length=1, description="Primary speaker / author for provenance"
    )
    reference_time: datetime = Field(..., description="Timezone-aware UTC timestamp")

    @field_validator("chat_id")
    @classmethod
    def _validate_chat_id(cls, v: int) -> int:
        if v == 0:
            raise ValueError("chat_id must not be 0")
        return v

    @field_validator("reference_time")
    @classmethod
    def _ensure_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v.astimezone(UTC)

    @property
    def formatted_text(self) -> str:
        """Alias for compatibility with DialogueEpisode interface."""
        return self.text


class CheckpointStateContract(BaseModel):
    """Runtime contract for importing checkpoint state persistence."""

    model_config = ConfigDict(extra="ignore")

    chat_id: int = Field(...)
    chat_title: str = Field(default="")
    export_file: str = Field(default="")
    total_episodes: int = Field(ge=0, default=0)
    processed_indices: list[int] = Field(default_factory=list)
    last_processed_index: int = Field(default=-1)
    completed: bool = Field(default=False)
    updated_at: str = Field(default="")

    @field_validator("chat_id")
    @classmethod
    def _validate_chat_id(cls, v: int) -> int:
        if v == 0:
            raise ValueError("chat_id must not be 0")
        return v
