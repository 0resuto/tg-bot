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
        bot_language: str = "ru",
        admin_notifier: AdminNotifier | None = None,
    ) -> None:
        self.llm = llm
        self.memory_service = memory_service
        self.context_builder = context_builder
        self.persona_prompt = persona_prompt
        self.response_model = response_model
        self.bot_language = bot_language
        self.admin_notifier = admin_notifier

    async def generate_response(
        self,
        chat_id: int,
        user_display_name: str,
        active_user_names: list[str],
        *,
        bot_id: int = 0,
        memory_chat_ids: list[int] | None = None,
        raise_on_error: bool = False,
    ) -> str:
        """Generate a response using conversational context and memory."""
        effective_memory_chat_ids = memory_chat_ids if memory_chat_ids else [chat_id]

        # 1. Get conversation context
        context = await self.context_builder.get_context(chat_id)

        # 2. Get Level 1 quick facts for all active users across effective memory chats
        quick_facts: dict[str, list[MemoryFact]] = {}
        for name in active_user_names:
            all_name_facts: list[MemoryFact] = []
            seen_texts: set[str] = set()
            for m_chat_id in effective_memory_chat_ids:
                facts = await self.memory_service.get_quick_facts(user_name=name, chat_id=m_chat_id)
                for f in facts:
                    if f.fact_text not in seen_texts:
                        seen_texts.add(f.fact_text)
                        all_name_facts.append(f)
            if all_name_facts:
                quick_facts[name] = all_name_facts

        # 3. Get Level 2 deep search using recent conversation as query across effective memory chats
        query_lines = [f"{msg.display_name}: {msg.text}" for msg in context[-5:]] if context else []
        query_text = "\n".join(query_lines)
        deep_facts: list[MemoryFact] = []
        if query_text:
            seen_deep_texts: set[str] = set()
            for m_chat_id in effective_memory_chat_ids:
                facts = await self.memory_service.search_memories(
                    query=query_text, chat_id=m_chat_id
                )
                for f in facts:
                    if f.fact_text not in seen_deep_texts:
                        seen_deep_texts.add(f.fact_text)
                        deep_facts.append(f)

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
                max_tokens=800,
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
                    logger.error("Failed to notify admin about LLM response error: %s", notify_err)
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
