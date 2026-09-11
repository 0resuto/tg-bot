"""Helper utilities for extracting textual and fallback representations of media messages."""

from __future__ import annotations

from aiogram.types import Message


def extract_message_content(message: Message, language: str = "ru") -> str | None:
    """Extract a human-readable textual representation of a message and any attachments.

    Acts as Level 1 multimodal fallback: provides context markers for photos, documents,
    audio, video, stickers, polls, etc., ensuring that conversation history and memory
    maintain awareness of non-textual message events.
    """
    text = getattr(message, "text", None)
    if text:
        return text.strip()

    caption = (getattr(message, "caption", None) or "").strip()
    is_ru = language.lower().startswith("ru")

    photo = getattr(message, "photo", None)
    if photo:
        tag = "[Фото]" if is_ru else "[Photo]"
        return f"{tag} {caption}".strip() if caption else tag

    document = getattr(message, "document", None)
    if document:
        doc_name = getattr(document, "file_name", None) or ("файл" if is_ru else "file")
        tag = f"[Документ: {doc_name}]" if is_ru else f"[Document: {doc_name}]"
        return f"{tag} {caption}".strip() if caption else tag

    voice = getattr(message, "voice", None)
    if voice:
        tag = "[Голосовое сообщение]" if is_ru else "[Voice message]"
        return f"{tag} {caption}".strip() if caption else tag

    audio = getattr(message, "audio", None)
    if audio:
        title = (
            getattr(audio, "title", None)
            or getattr(audio, "file_name", None)
            or ("аудио" if is_ru else "audio")
        )
        tag = f"[Аудио: {title}]" if is_ru else f"[Audio: {title}]"
        return f"{tag} {caption}".strip() if caption else tag

    video = getattr(message, "video", None)
    if video:
        tag = "[Видео]" if is_ru else "[Video]"
        return f"{tag} {caption}".strip() if caption else tag

    video_note = getattr(message, "video_note", None)
    if video_note:
        return "[Видеосообщение]" if is_ru else "[Video note]"

    sticker = getattr(message, "sticker", None)
    if sticker:
        emoji_val = getattr(sticker, "emoji", None)
        emoji = f" {emoji_val}" if emoji_val else ""
        return f"[Стикер{emoji}]" if is_ru else f"[Sticker{emoji}]"

    animation = getattr(message, "animation", None)
    if animation:
        tag = "[GIF]"
        return f"{tag} {caption}".strip() if caption else tag

    location = getattr(message, "location", None)
    if location:
        return "[Геолокация]" if is_ru else "[Location]"

    poll = getattr(message, "poll", None)
    if poll:
        question = getattr(poll, "question", "")
        return f"[Опрос: {question}]" if is_ru else f"[Poll: {question}]"

    contact = getattr(message, "contact", None)
    if contact:
        first = getattr(contact, "first_name", "")
        last = getattr(contact, "last_name", "") or ""
        contact_name = f"{first} {last}".strip()
        return f"[Контакт: {contact_name}]" if is_ru else f"[Contact: {contact_name}]"

    if caption:
        return caption

    return None
