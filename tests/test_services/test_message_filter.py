"""Unit tests for the JSON-configurable MessageNoiseFilter service."""

from __future__ import annotations

from datetime import datetime

from bot.models import ChatMessage
from bot.services.message_filter import MessageNoiseFilter


def test_noise_filter_filters_fillers():
    filter_service = MessageNoiseFilter()

    # Fillers and short reactions
    assert filter_service.is_meaningful_text("ок") is False
    assert filter_service.is_meaningful_text("OK") is False
    assert filter_service.is_meaningful_text("привет") is False
    assert filter_service.is_meaningful_text("спасибо") is False
    assert filter_service.is_meaningful_text("thx") is False
    assert filter_service.is_meaningful_text("лол") is False
    assert filter_service.is_meaningful_text("хаха") is False
    assert filter_service.is_meaningful_text("ахахаха") is False
    assert filter_service.is_meaningful_text("+++") is False
    assert filter_service.is_meaningful_text("?") is False

    # Standalone media tags
    assert filter_service.is_meaningful_text("[Photo]") is False
    assert filter_service.is_meaningful_text("[Sticker 👍]") is False
    assert filter_service.is_meaningful_text("[GIF]") is False
    assert filter_service.is_meaningful_text("[Voice message]") is False

    # Commands
    assert filter_service.is_meaningful_text("/start") is False
    assert filter_service.is_meaningful_text("/help") is False

    # Meaningful factual content
    assert filter_service.is_meaningful_text("Я переехал в новый офис на Тверской") is True
    assert filter_service.is_meaningful_text("У меня аллергия на арахис") is True
    assert (
        filter_service.is_meaningful_text("[Photo] Смотрите какую кошку я взял из приюта") is True
    )


def test_noise_filter_filter_batch():
    filter_service = MessageNoiseFilter()
    now = datetime.now()

    messages = [
        ChatMessage(
            chat_id=1,
            user_id=10,
            text="Привет",
            timestamp=now,
            message_id=1,
            display_name="Alice",
        ),
        ChatMessage(
            chat_id=1,
            user_id=10,
            text="[Sticker]",
            timestamp=now,
            message_id=2,
            display_name="Alice",
        ),
        ChatMessage(
            chat_id=1,
            user_id=10,
            text="Я сегодня защитила диплом по биохимии!",
            timestamp=now,
            message_id=3,
            display_name="Alice",
        ),
        ChatMessage(
            chat_id=1,
            user_id=10,
            text="ахаха",
            timestamp=now,
            message_id=4,
            display_name="Alice",
        ),
    ]

    filtered = filter_service.filter_batch(messages)
    assert len(filtered) == 1
    assert filtered[0].message_id == 3
    assert filtered[0].text == "Я сегодня защитила диплом по биохимии!"
