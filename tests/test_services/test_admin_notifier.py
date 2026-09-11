from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from bot.services.admin_notifier import AdminNotifier


@pytest.mark.asyncio
async def test_notify_error_with_bot():
    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock()

    notifier = AdminNotifier(admin_chat_id=123456, bot=mock_bot)
    err = ValueError("Something went wrong")

    await notifier.notify_error(
        chat_id=-100123,
        user_display_name="Alice",
        error=err,
        context_info="Generating reply",
    )

    assert mock_bot.send_message.call_count == 1
    call_kwargs = mock_bot.send_message.call_args.kwargs
    assert call_kwargs["chat_id"] == 123456
    text = call_kwargs["text"]
    assert "-100123" in text
    assert "Alice" in text
    assert "ValueError" in text
    assert "Something went wrong" in text
    assert "Generating reply" in text


@pytest.mark.asyncio
async def test_notify_error_without_bot():
    notifier = AdminNotifier(admin_chat_id=123456, bot=None)
    # Should not raise exception when bot is not set
    await notifier.notify_error(
        chat_id=-100123,
        user_display_name="Alice",
        error=RuntimeError("No bot"),
    )


@pytest.mark.asyncio
async def test_notify_error_without_admin_chat_id():
    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock()

    notifier = AdminNotifier(admin_chat_id=None, bot=mock_bot)
    await notifier.notify_error(
        chat_id=-100123,
        user_display_name="Alice",
        error=RuntimeError("No admin chat"),
    )
    assert mock_bot.send_message.call_count == 0


@pytest.mark.asyncio
async def test_notify_error_send_exception():
    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock(side_effect=RuntimeError("Telegram network timeout"))

    notifier = AdminNotifier(admin_chat_id=123456, bot=mock_bot)
    # Must catch the error internally and not raise
    await notifier.notify_error(
        chat_id=-100123,
        user_display_name="Alice",
        error=ValueError("Failure"),
    )


@pytest.mark.asyncio
async def test_notify_error_truncation():
    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock()

    notifier = AdminNotifier(admin_chat_id=123456, bot=mock_bot)
    long_error = "x" * 2000

    await notifier.notify_error(
        chat_id=-100123,
        user_display_name="Alice",
        error=ValueError(long_error),
    )

    text = mock_bot.send_message.call_args.kwargs["text"]
    assert "[truncated]" in text
