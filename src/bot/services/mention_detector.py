from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

import cyrtranslit


class MentionDetector:
    """Detects when the bot is mentioned in text messages."""

    def __init__(
        self, bot_names: list[str], bot_user_id: int, bot_username: str | None = None
    ) -> None:
        self.bot_user_id = bot_user_id
        self.bot_username = bot_username

        patterns = []
        for name in bot_names:
            patterns.extend(self._generate_variants(name))

        # Compile a single regex pattern with \b word boundaries
        pattern_str = r"\b(" + "|".join(re.escape(p) for p in patterns) + r")\b"
        self._pattern = re.compile(pattern_str, re.UNICODE | re.IGNORECASE)

    def _generate_variants(self, name: str) -> list[str]:
        """Generate transliterated and declension variants for a given name."""
        variants = set()

        # Add original name
        variants.add(name)

        # Add transliterated variants
        cyrillic = cyrtranslit.to_cyrillic(name, "ru")
        latin = cyrtranslit.to_latin(name, "ru")

        variants.add(cyrillic)
        variants.add(latin)

        # Generate Russian noun declension variants for names ending in 'a' or 'ya'
        for variant in list(variants):
            if variant.lower().endswith("а") or variant.lower().endswith("я"):
                base = variant[:-1]
                variants.add(base + "ы")  # Genitive
                variants.add(base + "е")  # Dative
                variants.add(base + "у")  # Accusative
                variants.add(base + "ой")  # Instrumental

        return list(variants)

    def is_mentioned_in_text(self, text: str) -> bool:
        """Check if the bot's name is mentioned in the text."""
        return bool(self._pattern.search(text))

    def is_bot_replied_to(self, reply_to_user_id: int | None) -> bool:
        """Check if the message is a reply to the bot."""
        return reply_to_user_id == self.bot_user_id

    def is_bot_mentioned_entity(
        self, text: str, entities: Sequence[Any] | None, bot_username: str | None
    ) -> bool:
        """Check Telegram mention entities."""
        if not entities or not bot_username:
            return False

        bot_mention = f"@{bot_username}".lower()
        for entity in entities:
            ent_type = (
                entity.get("type") if isinstance(entity, dict) else getattr(entity, "type", None)
            )
            if str(ent_type).lower() in ("mention", "messageentitytype.mention"):
                if hasattr(entity, "extract_from"):
                    mention_text = entity.extract_from(text)
                elif hasattr(entity, "text") and entity.text:
                    mention_text = entity.text
                else:
                    offset = (
                        entity.get("offset", 0)
                        if isinstance(entity, dict)
                        else getattr(entity, "offset", 0)
                    )
                    length = (
                        entity.get("length", 0)
                        if isinstance(entity, dict)
                        else getattr(entity, "length", 0)
                    )
                    mention_text = text[offset : offset + length]

                if mention_text and mention_text.lower() == bot_mention:
                    return True
        return False

    def is_addressed(
        self, text: str, entities: Sequence[dict] | None = None, reply_to_user_id: int | None = None
    ) -> bool:
        """Combined check for any form of bot addressing."""
        return (
            self.is_bot_replied_to(reply_to_user_id)
            or self.is_bot_mentioned_entity(text, entities, self.bot_username)
            or self.is_mentioned_in_text(text)
        )
