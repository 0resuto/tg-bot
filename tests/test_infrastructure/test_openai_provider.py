"""Tests for OpenAILLMProvider."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import openai
import pytest

from bot.config import Settings
from bot.domain.enums import OperationType
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
        default_chat_id=123,
        timeout=42.0,
    )
    assert provider.timeout == 42.0
    assert provider.default_model == "gpt-4o"
    assert provider.default_chat_id == 123
    assert provider.client.timeout == 42.0


@pytest.mark.asyncio
async def test_openai_provider_generate_response_success():
    """Verify successful response generation."""
    provider = OpenAILLMProvider(api_key="test-key", default_model="gpt-4o", default_chat_id=100)

    mock_choice = MagicMock()
    mock_choice.message.content = "Hello, world!"
    mock_usage = MagicMock()
    mock_usage.prompt_tokens = 10
    mock_usage.completion_tokens = 5
    mock_usage.total_tokens = 15

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_response.usage = mock_usage

    provider.client.chat.completions.create = AsyncMock(return_value=mock_response)

    content, record = await provider.generate_response(
        system_prompt="System prompt",
        messages=[{"role": "user", "content": "Hi"}],
    )

    assert content == "Hello, world!"
    assert record.chat_id == 100
    assert record.model == "gpt-4o"
    assert record.prompt_tokens == 10
    assert record.completion_tokens == 5
    assert record.total_tokens == 15
    assert record.operation == OperationType.RESPONSE


@pytest.mark.asyncio
async def test_openai_provider_retries_on_api_timeout():
    """Verify APITimeoutError triggers retry and succeeds on second attempt."""
    provider = OpenAILLMProvider(api_key="test-key", default_model="gpt-4o")

    mock_choice = MagicMock()
    mock_choice.message.content = "Recovered response"
    mock_usage = MagicMock()
    mock_usage.prompt_tokens = 8
    mock_usage.completion_tokens = 4
    mock_usage.total_tokens = 12

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_response.usage = mock_usage

    dummy_request = MagicMock()
    timeout_err = openai.APITimeoutError(request=dummy_request)

    # First attempt raises APITimeoutError, second succeeds
    provider.client.chat.completions.create = AsyncMock(side_effect=[timeout_err, mock_response])

    content, record = await provider.generate_response(
        system_prompt="System",
        messages=[{"role": "user", "content": "Test"}],
    )

    assert content == "Recovered response"
    assert record.total_tokens == 12
    assert provider.client.chat.completions.create.call_count == 2
