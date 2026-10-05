from __future__ import annotations

import asyncio
import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from bot.log import get_logger
from bot.models import ChatMessage, EmptyLLMResponseError, LLMProvider, MemoryFact
from bot.services.context_builder import ContextBuilder
from bot.services.memory_service import MemoryService
from bot.services.time_window import extract_time_window

if TYPE_CHECKING:
    from bot.services.admin_notifier import AdminNotifier

logger = get_logger(__name__)


class ResponseService:
    """Generates bot responses using the LLM with memory context."""

    def __init__(
        self,
        llm: LLMProvider,
        memory_service: MemoryService,
        context_builder: ContextBuilder,
        persona_prompt: str,
        response_model: str,
        admin_notifier: AdminNotifier | None = None,
        group_chat_id: int = 0,
        max_response_tokens: int = 1500,
        bot_timezone: str = "Europe/Moscow",
    ) -> None:
        self.llm = llm
        self.memory_service = memory_service
        self.context_builder = context_builder
        self.persona_prompt = persona_prompt
        self.response_model = response_model
        self.admin_notifier = admin_notifier
        self.group_chat_id = group_chat_id
        self.max_response_tokens = max_response_tokens
        self.timezone = ZoneInfo(bot_timezone)

    async def generate_response(
        self,
        chat_id: int,
        user_display_name: str,
        active_user_names: list[str],
        *,
        bot_id: int = 0,
        raise_on_error: bool = False,
    ) -> str:
        """Generate a response using conversational context and memory."""
        # 1. Get conversation context from current chat's short-term buffer
        context = await self.context_builder.get_context(chat_id)

        # Target chat for long-term memory: always the main group chat (unless explicitly in a separate group like simulator)
        if chat_id < 0 and self.group_chat_id != 0 and chat_id != self.group_chat_id:
            memory_chat_id = chat_id
        else:
            memory_chat_id = self.group_chat_id or chat_id

        # 2 & 3. Retrieve Level 1 quick facts and Level 2 deep facts concurrently
        # The latest message is the actual request. Joining several messages with
        # display names dilutes the query embedding and pushes relevant facts out
        # of the semantic top-N, so the deep search uses the request text alone.
        request_text = context[-1].text if context else ""
        query_text = request_text

        # Detect an explicit period in the latest request (e.g. "за неделю")
        valid_at_range = extract_time_window(request_text, now=datetime.now(UTC), tz=self.timezone)

        # Active participants: current speaker first, followed by other conversation participants
        speaker_name = self._sanitize_name(user_display_name)
        prioritized_users: list[str] = [speaker_name]
        for name in active_user_names:
            clean = self._sanitize_name(name)
            if clean and clean != speaker_name and clean not in prioritized_users:
                prioritized_users.append(clean)

        tasks = [
            self.memory_service.get_quick_facts(user_name=name, chat_id=memory_chat_id)
            for name in prioritized_users
        ]
        if query_text:
            tasks.append(
                self.memory_service.search_memories(
                    query=query_text,
                    chat_id=memory_chat_id,
                    valid_at_range=valid_at_range,
                )
            )

        results = await asyncio.gather(*tasks, return_exceptions=True) if tasks else []

        memory_unavailable = False
        quick_facts: dict[str, list[MemoryFact]] = {}
        for idx, name in enumerate(prioritized_users):
            res = results[idx]
            if isinstance(res, list) and res:
                quick_facts[name] = res
            elif isinstance(res, Exception):
                memory_unavailable = True
                logger.warning("Quick facts lookup failed", user_name=name, error=str(res))

        deep_facts: list[MemoryFact] = []
        if query_text and len(results) > len(prioritized_users):
            deep_res = results[-1]
            if isinstance(deep_res, list):
                deep_facts = deep_res
            elif isinstance(deep_res, Exception):
                memory_unavailable = True
                logger.warning("Deep memory search failed", error=str(deep_res))

        # 4. Build system prompt
        system_prompt = self._build_system_prompt(
            quick_facts, deep_facts, valid_at_range, memory_unavailable
        )

        # 5. Build messages list directly from context
        messages = self._build_messages(context, bot_id=bot_id)

        # 6. Call LLM provider
        try:
            response = await self.llm.generate_response(
                system_prompt=system_prompt,
                messages=messages,
                model=self.response_model,
                max_tokens=self.max_response_tokens,
            )
            if not response or not response.strip():
                raise EmptyLLMResponseError(
                    "LLM returned an empty response "
                    f"(model={self.response_model}, max_tokens={self.max_response_tokens})"
                )
            return response.strip()
        except Exception as e:
            logger.error("Error generating LLM response", exc_info=e, chat_id=chat_id)
            if self.admin_notifier:
                try:
                    await self.admin_notifier.notify_error(
                        chat_id=chat_id,
                        user_display_name=user_display_name,
                        error=e,
                        context_info=(
                            f"Модель: {self.response_model}, "
                            f"лимит токенов ответа: {self.max_response_tokens}"
                        ),
                    )
                except Exception as notify_err:
                    logger.error(
                        "Failed to notify admin about LLM response error", error=str(notify_err)
                    )
            if raise_on_error:
                raise
            return "Извините, произошла ошибка при генерации ответа."

    def _build_system_prompt(
        self,
        quick_facts: dict[str, list[MemoryFact]],
        deep_facts: list[MemoryFact],
        valid_at_range: tuple[datetime, datetime] | None = None,
        memory_unavailable: bool = False,
    ) -> str:
        """Combines persona prompt with memory context section."""
        prompt_parts = [self.persona_prompt]

        local_now = datetime.now(UTC).astimezone(self.timezone)
        prompt_parts.append(
            f"\nCurrent date and time: {local_now.strftime('%Y-%m-%d %H:%M')} ({self.timezone.key})"
        )
        if valid_at_range is not None:
            start, end = valid_at_range
            prompt_parts.append(
                "Requested period: "
                f"{self._format_datetime(start, '%Y-%m-%d')} – "
                f"{self._format_datetime(end, '%Y-%m-%d')} "
                f"({self.timezone.key})"
            )
            prompt_parts.append(
                "Facts prefixed with a date belong to that date; facts without a date "
                "are background only and must not be presented as events of the period."
            )
            if not memory_unavailable:
                has_period_facts = bool(deep_facts) or any(
                    self._fact_in_window(fact, start, end)
                    for facts in quick_facts.values()
                    for fact in facts
                )
                if not has_period_facts:
                    prompt_parts.append(
                        "No dated memories were found for the requested period. "
                        "If asked about this period, state that there are no recorded "
                        "events for it."
                    )

        if memory_unavailable:
            prompt_parts.append(
                "Memory storage is temporarily unavailable right now. Do not claim "
                "that no events were recorded; tell the user that memory is "
                "temporarily unavailable and suggest trying again later."
            )

        if quick_facts or deep_facts:
            prompt_parts.append("\nWhat you remember about the participants:")

            for user_name, facts in quick_facts.items():
                safe_user = self._sanitize_name(user_name)
                prompt_parts.append(f"- {safe_user}:")
                for fact in facts:
                    prompt_parts.append(f"  * {self._format_fact(fact)}")

            if deep_facts:
                prompt_parts.append("- Relevant conversational memories:")
                for fact in deep_facts:
                    prompt_parts.append(f"  * {self._format_fact(fact)}")

        return "\n".join(prompt_parts)

    def _format_fact(self, fact: MemoryFact) -> str:
        """Render a fact with its event date when known, sanitizing newlines."""
        clean_fact = fact.fact_text.replace("\r", " ").replace("\n", " ").strip()
        event_time = fact.valid_at or fact.reference_time
        if event_time is None:
            return clean_fact
        return f"[{self._format_datetime(event_time, '%Y-%m-%d')}] {clean_fact}"

    def _fact_in_window(self, fact: MemoryFact, start: datetime, end: datetime) -> bool:
        """Return True if the fact's known event time falls into [start, end)."""
        event_time = fact.valid_at or fact.reference_time
        if event_time is None:
            return False
        if event_time.tzinfo is None:
            event_time = event_time.replace(tzinfo=UTC)
        return start <= event_time < end

    def _format_datetime(self, dt: datetime, fmt: str) -> str:
        """Render a datetime in the configured timezone (naive values are UTC)."""
        aware = dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt
        return aware.astimezone(self.timezone).strftime(fmt)

    @staticmethod
    def _sanitize_name(name: str) -> str:
        """Sanitizes user display names to prevent prompt injection and formatting breaks."""
        if not name:
            return "User"
        cleaned = re.sub(r"[\r\n\t]", " ", name)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()[:64]
        return cleaned or "User"

    def _build_messages(
        self,
        context: list[ChatMessage],
        bot_id: int = 0,
    ) -> list[dict[str, str]]:
        """Converts ChatMessage list to OpenAI-style message dicts."""
        messages: list[dict[str, str]] = []
        for msg in context:
            timestamp = self._format_datetime(msg.timestamp, "%Y-%m-%d %H:%M")
            if bot_id and msg.user_id == bot_id:
                messages.append({"role": "assistant", "content": f"[{timestamp}] {msg.text}"})
            else:
                safe_name = self._sanitize_name(msg.display_name)
                messages.append(
                    {"role": "user", "content": f"[{timestamp}] {safe_name}: {msg.text}"}
                )
        return messages
