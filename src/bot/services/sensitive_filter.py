from __future__ import annotations

import re

from bot.domain.enums import SensitiveCategory
from bot.log import get_logger

logger = get_logger(__name__)


class SensitiveFilter:
    """Pre-ingestion filter that scans text for sensitive content and redacts/skips it."""

    # Default regex patterns for each category (English and Russian)
    DEFAULT_PATTERNS = {
        SensitiveCategory.HEALTH: r"\b(medical|diagnosis|prescription|disease|illness|symptom|болезнь|диагноз|рецепт|симптом|больница|лекарство)\b",
        SensitiveCategory.FINANCE: r"\b(salary|income|debt|credit card|bank account|\$\d+|\d+\s*руб|зарплата|доход|долг|кредитка|счет|банк)\b",
        SensitiveCategory.CREDENTIALS: r"\b(password|api key|token|secret key|pin code|пароль|токен|секретный ключ|пин код)\b",
        SensitiveCategory.LEGAL: r"\b(arrested|court|lawsuit|immigration|deportation|criminal|арест|суд|иск|иммиграция|депортация|преступление)\b",
        SensitiveCategory.SEXUAL: r"\b(porn|sex|порно|секс|эротика)\b",
        SensitiveCategory.POLITICAL: r"\b(party membership|voting for|republican|democrat|партия|голосовать|выборы|политика)\b",
    }

    def __init__(self, enabled: bool, categories: list[str]) -> None:
        self.enabled = enabled
        self.active_categories = []

        # Compile patterns for active categories
        self.patterns: dict[SensitiveCategory, re.Pattern] = {}
        for cat_str in categories:
            try:
                cat = SensitiveCategory(cat_str.lower())
                self.active_categories.append(cat)
                pattern_str = self.DEFAULT_PATTERNS.get(cat, "")
                if pattern_str:
                    self.patterns[cat] = re.compile(pattern_str, re.IGNORECASE | re.UNICODE)
            except ValueError:
                logger.warning("Unknown sensitive category configured", category=cat_str)

    def scan(self, text: str) -> list[SensitiveCategory]:
        """Returns all detected sensitive categories in the text."""
        detected = []
        for cat, pattern in self.patterns.items():
            if pattern.search(text):
                detected.append(cat)
        return detected

    def should_skip(self, text: str) -> bool:
        """Returns True if text has CREDENTIALS category (always skip)."""
        return SensitiveCategory.CREDENTIALS in self.scan(text)

    def redact(self, text: str) -> str:
        """Replaces detected sensitive phrases with [REDACTED]."""
        redacted_text = text
        for pattern in self.patterns.values():
            redacted_text = pattern.sub("[REDACTED]", redacted_text)
        return redacted_text

    def filter_for_ingestion(self, text: str) -> tuple[str | None, list[SensitiveCategory]]:
        """Main entry point: scan, redact, or skip text for ingestion."""
        if not self.enabled:
            return text, []

        categories = self.scan(text)

        if not categories:
            return text, []

        if SensitiveCategory.CREDENTIALS in categories:
            logger.info(
                "Message skipped due to credentials", categories=[c.value for c in categories]
            )
            return None, categories

        redacted_text = self.redact(text)
        logger.info(
            "Message redacted for sensitive content", categories=[c.value for c in categories]
        )
        return redacted_text, categories
