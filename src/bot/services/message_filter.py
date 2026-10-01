"""Heuristic message filter to prevent conversational noise from polluting the knowledge graph."""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from pathlib import Path

from bot.log import get_logger
from bot.models import ChatMessage

logger = get_logger(__name__)

DEFAULT_FILTER_WORDS: set[str] = {
    "ok",
    "okay",
    "yes",
    "no",
    "yep",
    "nope",
    "thanks",
    "thx",
    "pls",
    "please",
    "да",
    "нет",
    "ага",
    "неа",
    "ок",
    "ладно",
    "ясно",
    "понятно",
    "норм",
    "спс",
    "спасибо",
    "привет",
    "хай",
    "ку",
    "пока",
    "до встречи",
    "споки",
    "лол",
    "кек",
    "хаха",
    "хехе",
    "ахаха",
}

DEFAULT_MEDIA_TAGS: set[str] = {
    "[Photo]",
    "[Video]",
    "[Video note]",
    "[Voice message]",
    "[GIF]",
    "[Location]",
}


class MessageNoiseFilter:
    """Evaluates whether chat messages contain meaningful information worthy of graph memory."""

    def __init__(self, config_path: str | Path | None = None) -> None:
        self.min_length: int = 4
        self.ignore_prefixes: tuple[str, ...] = ("/",)
        self.standalone_media_tags: set[str] = set(DEFAULT_MEDIA_TAGS)
        self.sticker_prefix: str = "[Sticker"
        self.filler_words: set[str] = set(DEFAULT_FILTER_WORDS)
        self._regex_patterns: list[re.Pattern[str]] = []

        self._load_config(config_path)

    def _resolve_config_path(self, config_path: str | Path | None) -> Path | None:
        """Resolve config path across current working directory and source tree."""
        if config_path:
            p = Path(config_path)
            if p.is_file():
                return p

        # Check relative to working directory
        cwd_path = Path("prompts/noise_filter.json")
        if cwd_path.is_file():
            return cwd_path

        # Check relative to package location
        pkg_path = Path(__file__).resolve().parent.parent.parent / "prompts" / "noise_filter.json"
        if pkg_path.is_file():
            return pkg_path

        return None

    def _load_config(self, config_path: str | Path | None) -> None:
        """Load filter configuration from JSON file or fall back to defaults."""
        target_path = self._resolve_config_path(config_path)
        if not target_path:
            logger.debug("Noise filter JSON file not found; using fallback default rules")
            return

        try:
            content = target_path.read_text(encoding="utf-8")
            data = json.loads(content)
            self.min_length = int(data.get("min_length", 4))
            self.ignore_prefixes = tuple(data.get("ignore_prefixes", ["/"]))
            self.standalone_media_tags = set(data.get("standalone_media_tags", DEFAULT_MEDIA_TAGS))
            self.sticker_prefix = str(data.get("sticker_prefix", "[Sticker"))
            self.filler_words = {str(w).strip().lower() for w in data.get("filler_words", [])}

            patterns = data.get("regex_patterns", [])
            self._regex_patterns = [
                re.compile(pat, re.IGNORECASE) for pat in patterns if isinstance(pat, str) and pat
            ]
            logger.debug(
                "Noise filter rules loaded from JSON",
                path=str(target_path),
                filler_count=len(self.filler_words),
            )
        except Exception as exc:
            logger.warning("Failed to load noise filter JSON; retaining defaults", error=str(exc))

    def is_meaningful_text(self, text: str) -> bool:
        """Check if message text contains meaningful factual content."""
        clean = text.strip()
        if not clean:
            return False

        # Ignore commands
        if any(clean.startswith(prefix) for prefix in self.ignore_prefixes):
            return False

        # Ignore standalone media tags without text descriptions
        if clean in self.standalone_media_tags:
            return False

        # Ignore stickers without caption
        if clean.startswith(self.sticker_prefix):
            return False

        # Ignore text too short to contain a fact
        if len(clean) < self.min_length:
            return False

        # Ignore filler words (case-insensitive)
        if clean.lower() in self.filler_words:
            return False

        # Ignore custom regex patterns
        return all(not pattern.search(clean) for pattern in self._regex_patterns)

    def filter_batch(self, messages: Sequence[ChatMessage]) -> list[ChatMessage]:
        """Filter a list of buffered messages, keeping only informative entries."""
        return [msg for msg in messages if self.is_meaningful_text(msg.text)]


default_noise_filter = MessageNoiseFilter()
