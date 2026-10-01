"""Helper utilities for extracting textual representations of media messages."""

from __future__ import annotations

from aiogram.types import Message


def extract_message_content(message: Message) -> str | None:
    """Extract a human-readable textual representation of a message and any attachments.

    Acts as Level 1 multimodal fallback: provides context markers for photos, documents,
    audio, video, stickers, polls, etc., ensuring that conversation history and memory
    maintain awareness of non-textual message events.
    """
    text: str | None = getattr(message, "text", None)
    if text:
        return text.strip()

    caption = (getattr(message, "caption", None) or "").strip()

    photo = getattr(message, "photo", None)
    if photo:
        return f"[Photo] {caption}".strip() if caption else "[Photo]"

    document = getattr(message, "document", None)
    if document:
        doc_name = getattr(document, "file_name", None) or "file"
        tag = f"[Document: {doc_name}]"
        return f"{tag} {caption}".strip() if caption else tag

    voice = getattr(message, "voice", None)
    if voice:
        return f"[Voice message] {caption}".strip() if caption else "[Voice message]"

    audio = getattr(message, "audio", None)
    if audio:
        title = getattr(audio, "title", None) or getattr(audio, "file_name", None) or "audio"
        tag = f"[Audio: {title}]"
        return f"{tag} {caption}".strip() if caption else tag

    video = getattr(message, "video", None)
    if video:
        return f"[Video] {caption}".strip() if caption else "[Video]"

    video_note = getattr(message, "video_note", None)
    if video_note:
        return "[Video note]"

    sticker = getattr(message, "sticker", None)
    if sticker:
        emoji_val = getattr(sticker, "emoji", None)
        emoji = f" {emoji_val}" if emoji_val else ""
        return f"[Sticker{emoji}]"

    animation = getattr(message, "animation", None)
    if animation:
        return f"[GIF] {caption}".strip() if caption else "[GIF]"

    location = getattr(message, "location", None)
    if location:
        return "[Location]"

    poll = getattr(message, "poll", None)
    if poll:
        question = getattr(poll, "question", "")
        return f"[Poll: {question}]"

    contact = getattr(message, "contact", None)
    if contact:
        first = getattr(contact, "first_name", "")
        last = getattr(contact, "last_name", "") or ""
        contact_name = f"{first} {last}".strip()
        return f"[Contact: {contact_name}]"

    if caption:
        return caption

    return None
