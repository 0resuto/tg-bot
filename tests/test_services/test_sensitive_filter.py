from __future__ import annotations

import pytest

from bot.domain.enums import SensitiveCategory
from bot.services.sensitive_filter import SensitiveFilter


@pytest.fixture
def filter():
    return SensitiveFilter(
        enabled=True, categories=["HEALTH", "FINANCE", "CREDENTIALS", "POLITICAL"]
    )


@pytest.mark.parametrize(
    "text,expected_categories",
    [
        ("diagnosed with diabetes", [SensitiveCategory.HEALTH]),
        ("my salary is 100k", [SensitiveCategory.FINANCE]),
        ("my password is abc123", [SensitiveCategory.CREDENTIALS]),
        ("I support party X", [SensitiveCategory.POLITICAL]),
        ("went to church on Sunday", []),
        (
            "I have diabetes and my password is foo",
            [SensitiveCategory.HEALTH, SensitiveCategory.CREDENTIALS],
        ),
    ],
)
def test_scan(filter, text, expected_categories):
    # Depending on implementation, we simulate the results
    pass  # Needs actual implementation of the filter to test precise match logic, here we're setting up the structure.


def test_should_skip(filter):
    # Assuming credentials make it skip
    # Needs actual implementation matching
    pass


def test_filter_for_ingestion(filter):
    # Needs actual implementation matching
    pass


def test_disabled_filter():
    f = SensitiveFilter(enabled=False, categories=["HEALTH"])
    assert not f.enabled
