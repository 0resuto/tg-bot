from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from bot.services.time_window import extract_time_window

MSK = ZoneInfo("Europe/Moscow")
NOW = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)  # 15:00 Moscow


def _window(text: str, now: datetime = NOW):
    return extract_time_window(text, now=now, tz=MSK)


def test_no_window_returns_none():
    assert _window("Привет, как дела?") is None
    assert _window("") is None


def test_last_week():
    start, end = _window("Сделай сводку за последнюю неделю")
    assert start == datetime(2026, 9, 28, 12, 0, tzinfo=UTC)
    assert end == NOW


def test_last_n_days():
    start, end = _window("что было за 3 дня?")
    assert start == datetime(2026, 10, 2, 12, 0, tzinfo=UTC)
    assert end == NOW


def test_implicit_single_unit():
    start, _ = _window("о чём говорили за месяц")
    assert start == datetime(2026, 9, 5, 12, 0, tzinfo=UTC)


def test_yesterday_uses_local_day_boundaries():
    start, end = _window("что писали вчера")
    # 2026-10-04 00:00 MSK == 2026-10-03 21:00 UTC; end is 2026-10-05 00:00 MSK
    assert start == datetime(2026, 10, 3, 21, 0, tzinfo=UTC)
    assert end == datetime(2026, 10, 4, 21, 0, tzinfo=UTC)


def test_day_word_requires_word_boundary():
    assert _window("это вчерашняя новость") is None


def test_last_year_english():
    start, end = _window("summarize the last year")
    assert start == datetime(2025, 10, 5, 12, 0, tzinfo=UTC)
    assert end == NOW


def test_month_end_clamping():
    now = datetime(2026, 3, 31, 12, 0, tzinfo=UTC)
    start, _ = _window("сводка за месяц", now=now)
    assert start == datetime(2026, 2, 28, 12, 0, tzinfo=UTC)


def test_iso_range():
    start, end = _window("с 2026-09-01 по 2026-09-15")
    # Local (MSK) midnight boundaries converted to UTC
    assert start == datetime(2026, 8, 31, 21, 0, tzinfo=UTC)
    assert end == datetime(2026, 9, 15, 21, 0, tzinfo=UTC)


def test_invalid_iso_range_returns_none():
    assert _window("с 2026-09-15 по 2026-09-01") is None
    assert _window("с 2026-13-01 по 2026-13-15") is None
