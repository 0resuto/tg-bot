"""Unit tests for Contract-Driven Development schemas and runtime validation."""

from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from bot.models import ChatMessage
from tools.chat_importer.contracts import (
    CheckpointStateContract,
    DialogueEpisodeContract,
    TelegramChatExportContract,
    TelegramMessageContract,
    TelegramTextEntityContract,
)


def test_telegram_text_entity_contract() -> None:
    """Validate text entity contract structure and immutability."""
    entity = TelegramTextEntityContract(type="bold", text="Highlighted", extra_field="ignored")  # type: ignore[call-arg]
    assert entity.type == "bold"
    assert entity.text == "Highlighted"

    with pytest.raises(ValidationError):
        entity.text = "mutated"  # type: ignore[misc]


def test_telegram_message_contract_valid_id() -> None:
    """Validate message ID parsing from integer and string representations."""
    msg1 = TelegramMessageContract(id=101, text="Hello")
    assert msg1.id == 101

    msg2 = TelegramMessageContract(id="202", text="World")  # type: ignore[arg-type]
    assert msg2.id == 202

    with pytest.raises(ValidationError):
        TelegramMessageContract(id="not-an-int")  # type: ignore[arg-type]


def test_telegram_message_contract_clean_text() -> None:
    """Validate get_clean_text with string, list, and fallback entities."""
    # Plain string
    msg_str = TelegramMessageContract(id=1, text="  Simple text  ")
    assert msg_str.get_clean_text() == "Simple text"

    # Mixed list
    msg_list = TelegramMessageContract(
        id=2,
        text=["Code: ", {"type": "code", "text": "print(1)"}, " done"],
    )
    assert msg_list.get_clean_text() == "Code: print(1) done"

    # Fallback to entities
    msg_entities = TelegramMessageContract(
        id=3,
        text="",
        text_entities=[TelegramTextEntityContract(type="plain", text="Entity fallback")],
    )
    assert msg_entities.get_clean_text() == "Entity fallback"


def test_telegram_message_contract_user_id_parsing() -> None:
    """Validate user ID parsing across all Telegram format variants."""
    assert TelegramMessageContract(id=1, from_id="user123456").get_user_id() == 123456
    assert TelegramMessageContract(id=2, from_id="channel7890").get_user_id() == 7890
    assert TelegramMessageContract(id=3, from_id=999).get_user_id() == 999
    assert TelegramMessageContract(id=4, from_id="user-100555").get_user_id() == -100555
    assert TelegramMessageContract(id=5, from_id=None).get_user_id() == 0
    assert TelegramMessageContract(id=6, from_id="invalid").get_user_id() == 0


def test_telegram_message_contract_timestamp_parsing() -> None:
    """Validate timestamp parsing from unixtime and ISO strings."""
    # Unixtime
    msg_unix = TelegramMessageContract(id=1, date_unixtime="1704067200")
    assert msg_unix.get_timestamp() == datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)

    # ISO string
    msg_iso = TelegramMessageContract(id=2, date="2024-06-15T10:30:00")
    assert msg_iso.get_timestamp() == datetime(2024, 6, 15, 10, 30, 0, tzinfo=UTC)

    # Fallback to current time
    msg_fallback = TelegramMessageContract(id=3, date="invalid-date")
    assert msg_fallback.get_timestamp().tzinfo == UTC


def test_telegram_chat_export_contract() -> None:
    """Validate top-level chat export contract."""
    raw_data: dict[str, Any] = {
        "id": 12345,
        "name": "  Engineering Team  ",
        "type": "public_supergroup",
        "messages": [
            {"id": 1, "type": "message", "text": "First"},
            {"id": 2, "type": "service", "action": "pin_message"},
        ],
    }
    chat = TelegramChatExportContract.model_validate(raw_data)
    assert chat.id == 12345
    assert chat.name == "Engineering Team"
    assert len(chat.messages) == 2
    assert chat.messages[0].id == 1
    assert chat.messages[1].type == "service"


def test_telegram_chat_export_contract_defaults() -> None:
    """Validate empty/none name defaults to Imported Chat."""
    chat = TelegramChatExportContract.model_validate({"name": None})
    assert chat.name == "Imported Chat"


def test_dialogue_episode_contract_invariants() -> None:
    """Validate runtime invariants on DialogueEpisodeContract."""
    t0 = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
    msg = ChatMessage(
        chat_id=-1001,
        user_id=1,
        text="Valid",
        timestamp=t0,
        message_id=1,
        display_name="Alice",
    )

    # Valid episode
    ep = DialogueEpisodeContract(
        episode_index=0,
        chat_id=-1001,
        messages=[msg],
        text="Alice: Valid",
        source_user_name="Alice",
        reference_time=t0,
    )
    assert ep.episode_index == 0
    assert ep.formatted_text == "Alice: Valid"

    # Invariant: episode_index >= 0
    with pytest.raises(ValidationError):
        DialogueEpisodeContract(
            episode_index=-1,
            chat_id=-1001,
            messages=[msg],
            text="Alice: Valid",
            source_user_name="Alice",
            reference_time=t0,
        )

    # Invariant: chat_id != 0
    with pytest.raises(ValidationError):
        DialogueEpisodeContract(
            episode_index=0,
            chat_id=0,
            messages=[msg],
            text="Alice: Valid",
            source_user_name="Alice",
            reference_time=t0,
        )

    # Invariant: messages must not be empty
    with pytest.raises(ValidationError):
        DialogueEpisodeContract(
            episode_index=0,
            chat_id=-1001,
            messages=[],
            text="Alice: Valid",
            source_user_name="Alice",
            reference_time=t0,
        )

    # Invariant: text must not be empty
    with pytest.raises(ValidationError):
        DialogueEpisodeContract(
            episode_index=0,
            chat_id=-1001,
            messages=[msg],
            text="",
            source_user_name="Alice",
            reference_time=t0,
        )

    # Invariant: source_user_name must not be empty
    with pytest.raises(ValidationError):
        DialogueEpisodeContract(
            episode_index=0,
            chat_id=-1001,
            messages=[msg],
            text="Alice: Valid",
            source_user_name="",
            reference_time=t0,
        )

    # Invariant: Naive datetime is automatically converted to UTC
    naive_t = datetime(2024, 1, 1, 12, 0, 0)
    ep_naive = DialogueEpisodeContract(
        episode_index=0,
        chat_id=-1001,
        messages=[msg],
        text="Alice: Valid",
        source_user_name="Alice",
        reference_time=naive_t,
    )
    assert ep_naive.reference_time.tzinfo == UTC


def test_checkpoint_state_contract() -> None:
    """Validate CheckpointStateContract serialization, deserialization and constraints."""
    contract = CheckpointStateContract(
        chat_id=-100123,
        chat_title="Main Chat",
        export_file="result.json",
        total_episodes=10,
        processed_indices=[0, 1, 2],
        last_processed_index=2,
        completed=False,
    )
    json_str = contract.model_dump_json()
    loaded = CheckpointStateContract.model_validate_json(json_str)

    assert loaded.chat_id == -100123
    assert loaded.total_episodes == 10
    assert loaded.processed_indices == [0, 1, 2]

    # Invariant: chat_id != 0
    with pytest.raises(ValidationError):
        CheckpointStateContract(chat_id=0)

    # Invariant: total_episodes >= 0
    with pytest.raises(ValidationError):
        CheckpointStateContract(chat_id=-1001, total_episodes=-5)
