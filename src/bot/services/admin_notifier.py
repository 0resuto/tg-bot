"""Admin alerting and notification service."""

from __future__ import annotations

import html
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from bot.log import get_logger

if TYPE_CHECKING:
    from aiogram import Bot

logger = get_logger(__name__)


class AdminNotifier:
    """Delivers critical diagnostic alerts and failure notifications to the system administrator."""

    def __init__(
        self,
        admin_chat_id: int | None = None,
        bot: Bot | None = None,
    ) -> None:
        self.admin_chat_id = admin_chat_id
        self.bot = bot
        self.recent_alerts: list[dict[str, Any]] = []
        self._subscribers: list[Any] = []

    def subscribe(self, callback: Any) -> None:
        """Register a callback invoked whenever an admin alert is dispatched."""
        if callback not in self._subscribers:
            self._subscribers.append(callback)

    def set_bot(self, bot: Bot) -> None:
        """Assign or update the active Telegram bot instance."""
        self.bot = bot

    async def notify_error(
        self,
        chat_id: int,
        user_display_name: str,
        error: Exception | str,
        context_info: str | None = None,
    ) -> None:
        """Send formatted alert message to administrator if configured."""
        error_type = type(error).__name__ if isinstance(error, Exception) else "RuntimeError"
        error_msg = str(error)

        if len(error_msg) > 1500:
            error_msg = error_msg[:1500] + "... [truncated]"

        alert_text = (
            "⚠️ <b>Ошибка при генерации ответа</b>\n\n"
            f"📍 <b>Чат:</b> <code>{chat_id}</code>\n"
            f"👤 <b>Пользователь:</b> {html.escape(user_display_name)}\n"
            f"❌ <b>Тип:</b> <code>{html.escape(error_type)}</code>\n"
            f"📝 <b>Детали:</b> <code>{html.escape(error_msg)}</code>"
        )
        if context_info:
            alert_text += f"\nℹ️ <b>Контекст:</b> {html.escape(context_info)}"

        logger.warning(
            "Admin alert triggered: chat_id=%s, user=%s, error=%s",
            chat_id,
            user_display_name,
            error_msg,
        )

        alert_entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "chat_id": chat_id,
            "user_display_name": user_display_name,
            "error_type": error_type,
            "error_msg": error_msg,
            "context_info": context_info,
            "formatted_text": alert_text,
            "sent_to_telegram": bool(self.admin_chat_id and self.bot),
        }
        self.recent_alerts.append(alert_entry)
        if len(self.recent_alerts) > 50:
            self.recent_alerts.pop(0)

        for sub in self._subscribers:
            try:
                sub(alert_entry)
            except Exception as sub_err:
                logger.error("Error in alert subscriber", error=str(sub_err))

        if not self.admin_chat_id or not self.bot:
            logger.warning(
                "Admin notification skipped for Telegram: bot or admin_chat_id not configured. "
                "(Set TELEGRAM_BOT_TOKEN and ADMIN_CHAT_ID in .env to receive Telegram alerts)"
            )
            return

        try:
            await self.bot.send_message(
                chat_id=self.admin_chat_id,
                text=alert_text,
                parse_mode="HTML",
            )
        except Exception as send_err:
            logger.error("Failed to send admin notification message", error=str(send_err))
