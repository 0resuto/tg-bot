from __future__ import annotations

import re
from typing import TYPE_CHECKING

from bot.domain.models import ChatMessage, MemoryFact
from bot.interfaces.llm import LLMProvider
from bot.log import get_logger
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
    ) -> None:
        self.llm = llm
        self.memory_service = memory_service
        self.context_builder = context_builder
        self.persona_prompt = persona_prompt
        self.response_model = response_model
        self.admin_notifier = admin_notifier
        self.group_chat_id = group_chat_id

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

        # 2. Get Level 1 quick facts for active users from main group memory
        quick_facts: dict[str, list[MemoryFact]] = {}
        for name in active_user_names:
            facts = await self.memory_service.get_quick_facts(
                user_name=name, chat_id=memory_chat_id
            )
            if facts:
                quick_facts[name] = facts

        # 3. Get Level 2 deep search using recent conversation as query against main group memory
        query_lines = [f"{msg.display_name}: {msg.text}" for msg in context[-5:]] if context else []
        query_text = "\n".join(query_lines)
        deep_facts: list[MemoryFact] = []
        if query_text:
            deep_facts = await self.memory_service.search_memories(
                query=query_text, chat_id=memory_chat_id
            )

        # 4. Build system prompt
        system_prompt = self._build_system_prompt(quick_facts, deep_facts)

        # 5. Build messages list with proper roles and sanitized names
        messages = self._build_messages(context, bot_id=bot_id)

        # 6. Call LLM provider
        try:
            return await self.llm.generate_response(
                system_prompt=system_prompt,
                messages=messages,
                model=self.response_model,
                temperature=0.7,
                max_tokens=250,
            )
        except Exception as e:
            logger.error("Error generating LLM response", exc_info=e, chat_id=chat_id)
            if self.admin_notifier:
                try:
                    await self.admin_notifier.notify_error(
                        chat_id=chat_id,
                        user_display_name=user_display_name,
                        error=e,
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
                prompt_parts.append(f"- {user_name}:")
                for fact in facts:
                    prompt_parts.append(f"  * {fact.fact_text}")

            if deep_facts:
                prompt_parts.append("- Relevant conversational memories:")
                for fact in deep_facts:
                    prompt_parts.append(f"  * {fact.fact_text}")

        return "\n".join(prompt_parts)

    @staticmethod
    def _sanitize_name(name: str) -> str:
        """Sanitizes user display names to prevent prompt injection and formatting breaks."""
        if not name:
            return "User"
        cleaned = re.sub(r"[\r\n\t]", " ", name)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()[:64]
        return cleaned or "User"

    def _build_messages(self, context: list[ChatMessage], bot_id: int = 0) -> list[dict[str, str]]:
        """Converts ChatMessage list to OpenAI-style message dicts.

        Messages from the bot are assigned role 'assistant' without name prefix.
        User messages are assigned role 'user' with sanitized display names.
        """
        messages: list[dict[str, str]] = []
        for msg in context:
            if bot_id and msg.user_id == bot_id:
                messages.append({"role": "assistant", "content": msg.text})
            else:
                safe_name = self._sanitize_name(msg.display_name)
                messages.append({"role": "user", "content": f"{safe_name}: {msg.text}"})
        return messages
