from __future__ import annotations

import re
from collections.abc import Sequence

import cyrtranslit
from aiogram.enums import MessageEntityType
from aiogram.types import MessageEntity


class MentionDetector:
    """Detects when the bot is mentioned in text messages."""

    def __init__(
        self, bot_names: list[str], bot_user_id: int, bot_username: str | None = None
    ) -> None:
        self.bot_user_id = bot_user_id
        self.bot_username = bot_username

        patterns = []
        for name in bot_names:
            clean_name = name.strip()
            if clean_name:
                patterns.extend(self._generate_variants(clean_name))

        if patterns:
            # Compile a single regex pattern with \b word boundaries
            pattern_str = r"\b(" + "|".join(re.escape(p) for p in patterns) + r")\b"
            self._pattern: re.Pattern[str] | None = re.compile(
                pattern_str, re.UNICODE | re.IGNORECASE
            )
        else:
            self._pattern = None

    def _generate_variants(self, name: str) -> list[str]:
        """Generate transliterated variants for a given name."""
        variants = set()
        variants.add(name)

        # Add transliterated variants
        cyrillic = cyrtranslit.to_cyrillic(name, "ru")
        latin = cyrtranslit.to_latin(name, "ru")

        variants.add(cyrillic)
        variants.add(latin)

        return list(variants)

    def is_mentioned_in_text(self, text: str) -> bool:
        """Check if the bot's name is mentioned in the text."""
        if not self._pattern or not text:
            return False
        return bool(self._pattern.search(text))

    def is_bot_replied_to(self, reply_to_user_id: int | None) -> bool:
        """Check if the message is a reply to the bot."""
        return reply_to_user_id == self.bot_user_id

    def is_bot_mentioned_entity(
        self, text: str, entities: Sequence[MessageEntity] | None, bot_username: str | None
    ) -> bool:
        """Check Telegram mention entities."""
        if not entities or not bot_username or not text:
            return False

        bot_mention = f"@{bot_username}".lower()
        for entity in entities:
            if entity.type == MessageEntityType.MENTION:
                if entity.offset < 0 or entity.length <= 0:
                    continue
                mention_text = entity.extract_from(text)
                if mention_text and mention_text.lower() == bot_mention:
                    return True
        return False

    def is_addressed(
        self,
        text: str,
        entities: Sequence[MessageEntity] | None = None,
        reply_to_user_id: int | None = None,
    ) -> bool:
        """Combined check for any form of bot addressing."""
        return (
            self.is_bot_replied_to(reply_to_user_id)
            or self.is_bot_mentioned_entity(text, entities, self.bot_username)
            or self.is_mentioned_in_text(text)
        )
