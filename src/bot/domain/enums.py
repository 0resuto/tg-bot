"""Domain enumerations used across the application."""

from __future__ import annotations

from enum import StrEnum


class MemoryLevel(StrEnum):
    """Memory retrieval depth."""

    QUICK = "quick"
    DEEP = "deep"


class SensitiveCategory(StrEnum):
    """Categories of information excluded from long-term memory."""

    HEALTH = "health"
    FINANCE = "finance"
    CREDENTIALS = "credentials"
    LEGAL = "legal"
    SEXUAL = "sexual"
    POLITICAL = "political"
