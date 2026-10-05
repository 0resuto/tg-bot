"""Parse natural-language time windows (RU/EN) into UTC datetime ranges."""

from __future__ import annotations

import calendar
import re
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

_RU_UNIT = r"минут\w*|час\w*|день|дня|дней|дн\w*|суток|сутки|недел\w*|месяц\w*|год\w*|лет"

_RELATIVE_RE = re.compile(
    r"(?:за\s+(?:последн\w+\s+)?|последн\w+\s+|прошл\w+\s+)"
    r"(?P<num>\d+)?\s*(?P<unit>" + _RU_UNIT + r")",
    re.IGNORECASE,
)

_EN_RELATIVE_RE = re.compile(
    r"\b(?:last|past)\s+(?P<num>\d+)?\s*"
    r"(?P<unit>minutes?|hours?|days?|weeks?|months?|years?)\b",
    re.IGNORECASE,
)

_ISO_RANGE_RE = re.compile(
    r"\bс\s+(\d{4})-(\d{2})-(\d{2})\s+по\s+(\d{4})-(\d{2})-(\d{2})\b",
    re.IGNORECASE,
)

_DAY_WORD_RE = re.compile(r"\b(позавчера|вчера|сегодня|yesterday|today)\b", re.IGNORECASE)


def extract_time_window(
    text: str, *, now: datetime, tz: ZoneInfo
) -> tuple[datetime, datetime] | None:
    """Extract a UTC ``(start, end)`` window from a user request, if any.

    Recognizes relative periods ("за последнюю неделю", "за 3 дня", "last month"),
    day words ("вчера", "сегодня") and explicit ISO ranges ("с 2026-09-01 по
    2026-09-15"). Returns ``None`` when no window is mentioned.
    """
    if not text:
        return None
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    local_now = now.astimezone(tz)

    day_match = _DAY_WORD_RE.search(text)
    if day_match:
        word = day_match.group(1).lower()
        day_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
        if word == "позавчера":
            return _to_utc(day_start - timedelta(days=2), tz), _to_utc(day_start - timedelta(1), tz)
        if word in {"вчера", "yesterday"}:
            return _to_utc(day_start - timedelta(1), tz), _to_utc(day_start, tz)
        return _to_utc(day_start, tz), _to_utc(local_now, tz)

    iso_match = _ISO_RANGE_RE.search(text)
    if iso_match:
        try:
            start_local = datetime(
                int(iso_match.group(1)),
                int(iso_match.group(2)),
                int(iso_match.group(3)),
                tzinfo=tz,
            )
            end_local = datetime(
                int(iso_match.group(4)),
                int(iso_match.group(5)),
                int(iso_match.group(6)),
                tzinfo=tz,
            ) + timedelta(days=1)
        except ValueError:
            return None
        if start_local >= end_local:
            return None
        return _to_utc(start_local, tz), _to_utc(end_local, tz)

    relative_match = _RELATIVE_RE.search(text) or _EN_RELATIVE_RE.search(text)
    if relative_match is None:
        return None

    raw_num = relative_match.group("num")
    num = int(raw_num) if raw_num else 1
    if num <= 0:
        return None
    try:
        start_local = _subtract(local_now, relative_match.group("unit"), num)
    except (OverflowError, ValueError):
        return None
    return _to_utc(start_local, tz), _to_utc(local_now, tz)


def _to_utc(dt: datetime, tz: ZoneInfo) -> datetime:
    """Convert a local aware datetime to UTC."""
    return dt.replace(tzinfo=tz).astimezone(UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def _subtract(now_local: datetime, unit: str, num: int) -> datetime:
    """Subtract ``num`` of ``unit`` from a local datetime (calendar-aware months)."""
    unit = unit.lower()
    if unit.startswith(("минут", "minute")):
        return now_local - timedelta(minutes=num)
    if unit.startswith(("час", "hour")):
        return now_local - timedelta(hours=num)
    if unit.startswith(("дн", "сут", "day")):
        return now_local - timedelta(days=num)
    if unit.startswith(("недел", "week")):
        return now_local - timedelta(weeks=num)
    if unit.startswith(("месяц", "month")):
        return _shift_months(now_local, num)
    return _shift_months(now_local, num * 12)


def _shift_months(dt: datetime, months: int) -> datetime:
    """Shift a datetime by ``months``, clamping the day to the target month."""
    month_index = dt.month - 1 - months
    year = dt.year + month_index // 12
    month = month_index % 12 + 1
    day = min(dt.day, calendar.monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day)
