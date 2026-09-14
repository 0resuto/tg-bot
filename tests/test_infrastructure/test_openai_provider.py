"""Tests for OpenAILLMProvider."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import openai
import pytest

from bot.config import Settings
from bot.infrastructure.llm.openai_provider import OpenAILLMProvider


def test_openai_provider_timeout_config():
    """Verify default timeout setting in config."""
    settings = Settings()
    assert settings.openai_timeout_seconds == 60.0


def test_openai_provider_initialization():
    """Verify provider initializes with custom timeout."""
    provider = OpenAILLMProvider(
        api_key="test-key",
        default_model="gpt-4o",
        timeout=42.0,
    )
    assert provider.timeout == 42.0
    assert provider.default_model == "gpt-4o"
    assert provider.client.timeout == 42.0


@pytest.mark.asyncio
async def test_openai_provider_generate_response_success():
    """Verify successful response generation."""
    provider = OpenAILLMProvider(api_key="test-key", default_model="gpt-4o")

    mock_choice = MagicMock()
    mock_choice.message.content = "Hello, world!"

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    provider.client.chat.completions.create = AsyncMock(return_value=mock_response)

    content = await provider.generate_response(
        system_prompt="System prompt",
        messages=[{"role": "user", "content": "Hi"}],
    )

    assert content == "Hello, world!"


@pytest.mark.asyncio
async def test_openai_provider_retries_on_api_timeout():
    """Verify APITimeoutError triggers retry and succeeds on second attempt."""
    provider = OpenAILLMProvider(api_key="test-key", default_model="gpt-4o")

    mock_choice = MagicMock()
    mock_choice.message.content = "Recovered response"

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    dummy_request = MagicMock()
    timeout_err = openai.APITimeoutError(request=dummy_request)

    # First attempt raises APITimeoutError, second succeeds
    provider.client.chat.completions.create = AsyncMock(side_effect=[timeout_err, mock_response])

    content = await provider.generate_response(
        system_prompt="System",
        messages=[{"role": "user", "content": "Test"}],
    )

    assert content == "Recovered response"
    assert provider.client.chat.completions.create.call_count == 2
