from __future__ import annotations

import asyncio
import re
from typing import TYPE_CHECKING

from bot.log import get_logger
from bot.models import ChatMessage, EmptyLLMResponseError, LLMProvider, MemoryFact
from bot.services.context_builder import ContextBuilder
from bot.services.memory_service import MemoryService

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
    ) -> None:
        self.llm = llm
        self.memory_service = memory_service
        self.context_builder = context_builder
        self.persona_prompt = persona_prompt
        self.response_model = response_model
        self.admin_notifier = admin_notifier
        self.group_chat_id = group_chat_id
        self.max_response_tokens = max_response_tokens

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
        query_lines = [f"{msg.display_name}: {msg.text}" for msg in context[-5:]] if context else []
        query_text = "\n".join(query_lines)

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
                self.memory_service.search_memories(query=query_text, chat_id=memory_chat_id)
            )

        results = await asyncio.gather(*tasks, return_exceptions=True) if tasks else []

        quick_facts: dict[str, list[MemoryFact]] = {}
        for idx, name in enumerate(prioritized_users):
            res = results[idx]
            if isinstance(res, list) and res:
                quick_facts[name] = res
            elif isinstance(res, Exception):
                logger.warning("Quick facts lookup failed", user_name=name, error=str(res))

        deep_facts: list[MemoryFact] = []
        if query_text and len(results) > len(prioritized_users):
            deep_res = results[-1]
            if isinstance(deep_res, list):
                deep_facts = deep_res
            elif isinstance(deep_res, Exception):
                logger.warning("Deep memory search failed", error=str(deep_res))

        # 4. Build system prompt
        system_prompt = self._build_system_prompt(quick_facts, deep_facts)

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
        self, quick_facts: dict[str, list[MemoryFact]], deep_facts: list[MemoryFact]
    ) -> str:
        """Combines persona prompt with memory context section."""
        prompt_parts = [self.persona_prompt]

        if quick_facts or deep_facts:
            prompt_parts.append("\nWhat you remember about the participants:")

            for user_name, facts in quick_facts.items():
                safe_user = self._sanitize_name(user_name)
                prompt_parts.append(f"- {safe_user}:")
                for fact in facts:
                    clean_fact = fact.fact_text.replace("\r", " ").replace("\n", " ").strip()
                    prompt_parts.append(f"  * {clean_fact}")

            if deep_facts:
                prompt_parts.append("- Relevant conversational memories:")
                for fact in deep_facts:
                    clean_fact = fact.fact_text.replace("\r", " ").replace("\n", " ").strip()
                    prompt_parts.append(f"  * {clean_fact}")

        return "\n".join(prompt_parts)

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
            if bot_id and msg.user_id == bot_id:
                messages.append({"role": "assistant", "content": msg.text})
            else:
                safe_name = self._sanitize_name(msg.display_name)
                messages.append({"role": "user", "content": f"{safe_name}: {msg.text}"})
        return messages
