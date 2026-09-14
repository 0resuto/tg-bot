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


def test_is_addressed_dict_entities_with_emoji(detector):
    # Text: "🐶 @ista_bot"
    # '🐶' is 1 Python char, but 2 UTF-16 code units.
    # Space is 1 unit.
    # '@ista_bot' starts at UTF-16 offset 3, length 9 code units.
    text = "🐶 @ista_bot"
    entities = [{"type": "mention", "offset": 3, "length": 9}]
    assert detector.is_addressed(text, entities=entities)


def test_is_addressed_dict_entities_with_flag(detector):
    # Flag 🇺🇸 is 2 Regional Indicator code points, each is a surrogate pair (total 4 UTF-16 code units).
    # "🇺🇸 @ista_bot": flag (4) + space (1) = offset 5.
    text = "🇺🇸 @ista_bot"
    entities = [{"type": "mention", "offset": 5, "length": 9}]
    assert detector.is_addressed(text, entities=entities)


def test_is_addressed_dict_entities_cjk(detector):
    # CJK character "你" (1 code unit) + "好" (1 code unit) + space (1) = offset 3.
    text = "你好 @ista_bot"
    entities = [{"type": "mention", "offset": 3, "length": 9}]
    assert detector.is_addressed(text, entities=entities)


def test_is_addressed_dict_entities_invalid_offsets(detector):
    text = "Hello @ista_bot"
    # Negative offset
    assert not detector.is_bot_mentioned_entity(
        text, [{"type": "mention", "offset": -1, "length": 9}], "ista_bot"
    )
    # Zero or negative length
    assert not detector.is_bot_mentioned_entity(
        text, [{"type": "mention", "offset": 0, "length": 0}], "ista_bot"
    )
    # Out of bounds offset
    assert not detector.is_bot_mentioned_entity(
        text, [{"type": "mention", "offset": 100, "length": 9}], "ista_bot"
    )
