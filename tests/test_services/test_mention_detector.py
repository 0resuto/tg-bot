from __future__ import annotations

import pytest

from bot.services.mention_detector import MentionDetector


@pytest.fixture
def detector():
    return MentionDetector(
        bot_names=["Ista", "Бот"], bot_user_id=123456789, bot_username="ista_bot"
    )


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Привет, Ista!", True),
        ("Ista", True),
        ("ista, how are you?", True),
        ("ISTA is here", True),
        ("Иста, привет", True),
        ("иста, помоги", True),
        ("ИСТА, ответь", True),
        ("Тракториста", False),
        ("Батиста", False),
        ("distance", False),
        ("Привет, Бот!", True),
        ("бот, ты тут?", True),
        ("Работает", False),
        ("", False),
        ("Ista123", False),  # Assuming word boundaries
    ],
)
def test_is_mentioned_in_text(detector, text, expected):
    assert detector.is_mentioned_in_text(text) == expected


@pytest.mark.parametrize(
    "reply_to_user_id,expected",
    [
        (123456789, True),
        (987654321, False),
        (None, False),
    ],
)
def test_is_bot_replied_to(detector, reply_to_user_id, expected):
    assert detector.is_bot_replied_to(reply_to_user_id) == expected


def test_is_addressed_mention(detector):
    assert detector.is_addressed("Привет, Ista!")


def test_is_addressed_reply(detector):
    assert detector.is_addressed("Привет!", reply_to_user_id=123456789)


def test_is_addressed_none(detector):
    assert not detector.is_addressed("Привет всем!")


def test_is_addressed_entities(detector):
    # Mock some entities that contain @ista_bot
    class EntityMock:
        def __init__(self, text):
            self.type = "mention"
            self.text = text

        def extract_from(self, text):
            return self.text

    entities = [EntityMock("@ista_bot")]
    assert detector.is_addressed("Hello @ista_bot", entities=entities)
