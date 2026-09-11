"""Unit tests for media content extractor."""

from __future__ import annotations

from unittest.mock import MagicMock

from aiogram.types import (
    Audio,
    Contact,
    Document,
    Message,
    PhotoSize,
    Poll,
    Sticker,
    Voice,
)

from bot.telegram.media import extract_message_content


def test_extract_text_message():
    msg = MagicMock(spec=Message)
    msg.text = "Hello world"
    msg.caption = None
    assert extract_message_content(msg) == "Hello world"


def test_extract_photo_with_and_without_caption():
    msg = MagicMock(spec=Message)
    msg.text = None
    msg.photo = [MagicMock(spec=PhotoSize)]

    # Without caption (Russian default)
    msg.caption = None
    assert extract_message_content(msg, language="ru") == "[Фото]"
    assert extract_message_content(msg, language="en") == "[Photo]"

    # With caption
    msg.caption = "Look at this cat"
    assert extract_message_content(msg, language="ru") == "[Фото] Look at this cat"
    assert extract_message_content(msg, language="en") == "[Photo] Look at this cat"


def test_extract_document():
    doc = MagicMock(spec=Document)
    doc.file_name = "quarterly_report.pdf"

    msg = MagicMock(spec=Message)
    msg.text = None
    msg.document = doc

    msg.caption = None
    assert extract_message_content(msg, language="ru") == "[Документ: quarterly_report.pdf]"
    assert extract_message_content(msg, language="en") == "[Document: quarterly_report.pdf]"

    msg.caption = "Review urgently"
    assert (
        extract_message_content(msg, language="ru")
        == "[Документ: quarterly_report.pdf] Review urgently"
    )


def test_extract_voice_and_audio():
    msg = MagicMock(spec=Message)
    msg.text = None
    msg.caption = None
    msg.document = None
    msg.photo = None

    # Voice
    msg.voice = MagicMock(spec=Voice)
    msg.audio = None
    assert extract_message_content(msg, language="ru") == "[Голосовое сообщение]"
    assert extract_message_content(msg, language="en") == "[Voice message]"

    # Audio
    msg.voice = None
    audio = MagicMock(spec=Audio)
    audio.title = "Song Title"
    msg.audio = audio
    assert extract_message_content(msg, language="ru") == "[Аудио: Song Title]"
    assert extract_message_content(msg, language="en") == "[Audio: Song Title]"


def test_extract_sticker():
    msg = MagicMock(spec=Message)
    msg.text = None
    msg.caption = None
    msg.document = None
    msg.photo = None
    msg.voice = None
    msg.audio = None
    msg.video = None
    msg.video_note = None

    sticker = MagicMock(spec=Sticker)
    sticker.emoji = "🔥"
    msg.sticker = sticker

    assert extract_message_content(msg, language="ru") == "[Стикер 🔥]"
    assert extract_message_content(msg, language="en") == "[Sticker 🔥]"


def test_extract_poll_and_contact():
    msg = MagicMock(spec=Message)
    msg.text = None
    msg.caption = None
    msg.document = None
    msg.photo = None
    msg.voice = None
    msg.audio = None
    msg.video = None
    msg.video_note = None
    msg.sticker = None
    msg.animation = None
    msg.location = None

    # Poll
    poll = MagicMock(spec=Poll)
    poll.question = "Where to lunch?"
    msg.poll = poll
    msg.contact = None
    assert extract_message_content(msg, language="ru") == "[Опрос: Where to lunch?]"

    # Contact
    msg.poll = None
    contact = MagicMock(spec=Contact)
    contact.first_name = "Ivan"
    contact.last_name = "Petrov"
    msg.contact = contact
    assert extract_message_content(msg, language="ru") == "[Контакт: Ivan Petrov]"


def test_extract_empty_message():
    msg = MagicMock(spec=Message)
    msg.text = None
    msg.caption = None
    msg.photo = None
    msg.document = None
    msg.voice = None
    msg.audio = None
    msg.video = None
    msg.video_note = None
    msg.sticker = None
    msg.animation = None
    msg.location = None
    msg.poll = None
    msg.contact = None
    assert extract_message_content(msg) is None
