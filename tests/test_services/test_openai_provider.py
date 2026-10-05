"""Tests for OpenAILLMProvider."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import openai
import pytest

from bot.config import Settings
from bot.models import EmptyLLMResponseError
from bot.services.llm import OpenAILLMProvider


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
    provider.client.chat.completions.create.assert_awaited_once_with(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "System prompt"},
            {"role": "user", "content": "Hi"},
        ],
        max_completion_tokens=1000,
    )


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


@pytest.mark.asyncio
async def test_openai_provider_raises_on_empty_content():
    """Empty completion content must raise a diagnostic error instead of returning ''."""
    provider = OpenAILLMProvider(api_key="test-key", default_model="gpt-4o")

    mock_choice = MagicMock()
    mock_choice.message.content = None
    mock_choice.finish_reason = "length"

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    provider.client.chat.completions.create = AsyncMock(return_value=mock_response)

    with pytest.raises(EmptyLLMResponseError) as exc_info:
        await provider.generate_response(
            system_prompt="System",
            messages=[{"role": "user", "content": "Test"}],
            max_tokens=250,
        )

    message = str(exc_info.value)
    assert "empty response" in message
    assert "gpt-4o" in message
    assert "length" in message
    assert "250" in message


@pytest.mark.asyncio
async def test_openai_provider_raises_on_no_choices():
    """Missing choices must raise a diagnostic error."""
    provider = OpenAILLMProvider(api_key="test-key", default_model="gpt-4o")

    mock_response = MagicMock()
    mock_response.choices = []

    provider.client.chat.completions.create = AsyncMock(return_value=mock_response)

    with pytest.raises(EmptyLLMResponseError, match="no choices"):
        await provider.generate_response(
            system_prompt="System",
            messages=[{"role": "user", "content": "Test"}],
        )


@pytest.mark.asyncio
async def test_openai_provider_returns_truncated_content():
    """Partial content from a length-limited response is still returned."""
    provider = OpenAILLMProvider(api_key="test-key", default_model="gpt-4o")

    mock_choice = MagicMock()
    mock_choice.message.content = "Partial answer"
    mock_choice.finish_reason = "length"

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    provider.client.chat.completions.create = AsyncMock(return_value=mock_response)

    content = await provider.generate_response(
        system_prompt="System",
        messages=[{"role": "user", "content": "Test"}],
    )

    assert content == "Partial answer"


@pytest.mark.asyncio
async def test_openai_provider_close():
    """Verify provider close awaits client.close()."""
    provider = OpenAILLMProvider(api_key="test-key", default_model="gpt-4o")
    provider.client.close = AsyncMock()

    await provider.close()
    provider.client.close.assert_awaited_once()
