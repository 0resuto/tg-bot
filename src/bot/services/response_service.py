from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from bot.domain.models import ChatMessage, MemoryFact
from bot.interfaces.llm import LLMProvider
from bot.log import get_logger
from bot.repositories.token_usage_repo import TokenUsageRepository
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
        token_repo: TokenUsageRepository,
        persona_prompt: str,
        response_model: str,
        bot_language: str = "ru",
        admin_notifier: AdminNotifier | None = None,
    ) -> None:
        self.llm = llm
        self.memory_service = memory_service
        self.context_builder = context_builder
        self.token_repo = token_repo
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

        # 5. Build messages list
        messages = self._build_messages(context)

        # 6. Call LLM provider
        try:
            response_text, token_usage = await self.llm.generate_response(
                system_prompt=system_prompt,
                messages=messages,
                model=self.response_model,
                temperature=0.7,
                max_tokens=800,
            )

            # 7. Record token usage (telemetry failure should not drop response)
            try:
                token_usage = replace(token_usage, chat_id=chat_id)
                await self.token_repo.record_usage(token_usage)
            except Exception as usage_err:
                logger.error("Failed to record token usage", exc_info=usage_err, chat_id=chat_id)

            return response_text
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

    def _build_messages(self, context: list[ChatMessage]) -> list[dict[str, str]]:
        """Converts ChatMessage list to OpenAI-style message dicts."""
        return [{"role": "user", "content": f"{msg.display_name}: {msg.text}"} for msg in context]
