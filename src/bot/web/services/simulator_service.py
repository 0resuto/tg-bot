"""Service encapsulating the interactive chat simulator pipeline."""

from __future__ import annotations

import traceback
from datetime import UTC, datetime
from typing import Any

from bot.config import Settings
from bot.domain.models import ChatMessage, MemberIdentity
from bot.log import get_logger
from bot.repositories import MemberRepository
from bot.services.context_builder import ContextBuilder
from bot.services.debouncer import MessageDebouncer
from bot.services.mention_detector import MentionDetector
from bot.services.response_service import ResponseService
from bot.services.sensitive_filter import SensitiveFilter

logger = get_logger(__name__)

SIMULATOR_CHAT_ID = -1001987654321
SIMULATOR_BOT_USER_ID = 999999999

PRESET_USERS = [
    {"id": 1, "name": "Alice", "avatar": "👩", "role": "Member"},
    {"id": 2, "name": "Bob", "avatar": "👨", "role": "Member"},
    {"id": 3, "name": "Charlie", "avatar": "🧔", "role": "Member"},
    {"id": 10, "name": "Admin", "avatar": "👑", "role": "Admin"},
]


class ChatSimulatorService:
    """Manages simulated group messages, debounce timing, and bot responses in sandbox mode."""

    def __init__(
        self,
        settings: Settings,
        member_repo: MemberRepository | None,
        context_builder: ContextBuilder | None,
        debouncer: MessageDebouncer | None,
        mention_detector: MentionDetector | None,
        sensitive_filter: SensitiveFilter | None,
        response_service: ResponseService | None,
        admin_notifier: Any | None = None,
    ) -> None:
        self.settings = settings
        self.chat_id = SIMULATOR_CHAT_ID
        self.bot_user_id = SIMULATOR_BOT_USER_ID
        self.bot_names = settings.bot_name_list or ["Bot"]
        self.bot_username = f"{self.bot_names[0].lower()}_bot"

        self.member_repo = member_repo
        self.context_builder = context_builder
        self.debouncer = debouncer
        self.mention_detector = mention_detector
        self.sensitive_filter = sensitive_filter
        self.response_service = response_service
        self.admin_notifier = admin_notifier

        self.current_status = "ready"
        self.last_error: str | None = None
        self.logs: list[dict[str, Any]] = []
        self.turn_admin_alerts: list[dict[str, Any]] = []

        if self.admin_notifier and hasattr(self.admin_notifier, "subscribe"):
            self.admin_notifier.subscribe(self._on_admin_alert)

    def _on_admin_alert(self, alert: dict[str, Any]) -> None:
        self.turn_admin_alerts.append(alert)

    def log_event(self, event: dict[str, Any]) -> None:
        """Record diagnostic event in circular buffer."""
        self.logs.append(event)
        if len(self.logs) > 50:
            self.logs.pop(0)

    def get_presets(self) -> list[dict[str, str]]:
        """Return sample test scenarios for manual verification."""
        bot_name = self.bot_names[0]
        return [
            {"label": "Alice coffee", "text": "Я обожаю флэт уайт по утрам", "user": "Alice"},
            {"label": "Bob vacation", "text": "Вчера вернулся из отпуска в Риме!", "user": "Bob"},
            {
                "label": "Sensitive test",
                "text": "Моя зарплата 150000 рублей, а пароль admin123",
                "user": "Charlie",
            },
            {
                "label": f"Ask {bot_name}",
                "text": f"{bot_name}, что любит пить Алиса?",
                "user": "Bob",
            },
            {
                "label": "Substring test",
                "text": "Тракториста сегодня наградили за ударный труд",
                "user": "Alice",
            },
        ]

    async def send_simulated_message(
        self,
        user_id: int,
        user_name: str,
        text: str,
        reply_to_bot: bool = False,
    ) -> dict[str, Any]:
        """Process a simulated incoming message through the complete pipeline."""
        now = datetime.now(UTC)
        msg_id = int(now.timestamp() * 1000) % 1_000_000_000
        reply_to_msg_id = 999999 if reply_to_bot else None
        reply_to_user = self.bot_user_id if reply_to_bot else None

        self.turn_admin_alerts.clear()

        try:
            # 1. Register member identity
            identity = MemberIdentity(telegram_user_id=user_id, first_name=user_name)
            if self.member_repo:
                await self.member_repo.upsert_member(
                    chat_id=self.chat_id,
                    member=identity,
                    chat_title="Dev Test Group",
                )

            # 2. Build domain message
            chat_msg = ChatMessage(
                chat_id=self.chat_id,
                user_id=user_id,
                text=text,
                timestamp=now,
                message_id=msg_id,
                display_name=user_name,
                reply_to_message_id=reply_to_msg_id,
            )

            # 3. Context & Debounce
            if self.context_builder:
                await self.context_builder.add_message(chat_msg)
            if self.debouncer:
                await self.debouncer.on_message(chat_msg)

            # 4. Sensitive filter scan
            sensitive_cats: list[Any] = []
            redacted_text = text
            if self.sensitive_filter:
                redacted_text, sensitive_cats = self.sensitive_filter.filter_for_ingestion(text)
                if redacted_text is None:
                    redacted_text = "[REDACTED - SKIPPED FOR INGESTION]"

            # 5. Mention detection
            is_addressed = False
            trigger_reason = "Bot not addressed; message observed for memory"
            if self.mention_detector:
                is_addressed = self.mention_detector.is_addressed(
                    text=text,
                    reply_to_user_id=reply_to_user,
                )

            # 6. Response generation
            bot_reply: str | None = None
            if is_addressed:
                trigger_reason = "Bot was addressed directly or via reply"
                self.current_status = "calling_llm"
                if self.response_service:
                    recent_context = (
                        await self.context_builder.get_context(chat_id=self.chat_id)
                        if self.context_builder
                        else []
                    )
                    active_user_names = list(
                        {msg.display_name for msg in recent_context if msg.display_name}
                    )
                    bot_reply = await self.response_service.generate_response(
                        chat_id=self.chat_id,
                        user_display_name=user_name,
                        active_user_names=active_user_names,
                        bot_id=self.bot_user_id,
                    )
                    if bot_reply and self.context_builder:
                        bot_msg = ChatMessage(
                            chat_id=self.chat_id,
                            user_id=self.bot_user_id,
                            text=bot_reply,
                            timestamp=datetime.now(UTC),
                            message_id=msg_id + 1,
                            display_name=self.bot_names[0],
                            reply_to_message_id=msg_id,
                        )
                        await self.context_builder.add_message(bot_msg)
                if bot_reply and "произошла ошибка" in bot_reply.lower():
                    self.current_status = "error"
                    self.last_error = bot_reply
                    event_status = "error"
                else:
                    self.current_status = "ready"
                    event_status = "ok"

            self.log_event(
                {
                    "id": msg_id,
                    "timestamp": now.isoformat(),
                    "user_name": user_name,
                    "text": text,
                    "is_addressed": is_addressed,
                    "sensitive": [cat.value for cat in sensitive_cats],
                    "status": event_status if is_addressed else "ok",
                    "bot_reply": bot_reply,
                    "error": self.last_error
                    if is_addressed and self.current_status == "error"
                    else None,
                }
            )

            return {
                "success": True,
                "message": {
                    "id": msg_id,
                    "user_id": user_id,
                    "user_name": user_name,
                    "text": text,
                    "timestamp": now.isoformat(),
                },
                "is_addressed": is_addressed,
                "trigger_reason": trigger_reason,
                "sensitive_categories": [cat.value for cat in sensitive_cats],
                "redacted_text": redacted_text,
                "bot_reply": bot_reply,
                "bot_status": self.current_status,
                "bot_names": self.bot_names,
                "admin_alerts": list(self.turn_admin_alerts),
            }

        except Exception as exc:
            trace = traceback.format_exc()
            logger.error("Simulator message execution error", error=str(exc))
            self.current_status = "error"
            self.last_error = f"{type(exc).__name__}: {exc}"

            self.log_event(
                {
                    "id": msg_id,
                    "timestamp": now.isoformat(),
                    "user_name": user_name,
                    "text": text,
                    "status": "error",
                    "error": self.last_error,
                    "traceback": trace,
                }
            )

            return {
                "success": False,
                "error": self.last_error,
                "error_details": trace,
                "message": {
                    "id": msg_id,
                    "user_id": user_id,
                    "user_name": user_name,
                    "text": text,
                    "timestamp": now.isoformat(),
                },
                "is_addressed": False,
                "trigger_reason": f"Pipeline failure: {self.last_error}",
                "sensitive_categories": [],
                "redacted_text": text,
                "bot_reply": None,
                "bot_status": "error",
                "bot_names": self.bot_names,
                "admin_alerts": list(self.turn_admin_alerts),
            }
