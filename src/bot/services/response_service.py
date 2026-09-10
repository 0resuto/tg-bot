from __future__ import annotations

from bot.domain.models import ChatMessage, MemoryFact
from bot.interfaces.llm import LLMProvider
from bot.log import get_logger
from bot.repositories.token_usage_repo import TokenUsageRepository
from bot.services.context_builder import ContextBuilder
from bot.services.memory_service import MemoryService

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
    ) -> None:
        self.llm = llm
        self.memory_service = memory_service
        self.context_builder = context_builder
        self.token_repo = token_repo
        self.persona_prompt = persona_prompt
        self.response_model = response_model
        self.bot_language = bot_language

    async def generate_response(
        self,
        chat_id: int,
        user_display_name: str,
        active_user_names: list[str],
        *,
        raise_on_error: bool = False,
    ) -> str:
        """Generate a response using conversational context and memory."""

        # 1. Get conversation context
        context = await self.context_builder.get_context(chat_id)

        # 2. Get Level 1 quick facts for all active users
        quick_facts: dict[str, list[MemoryFact]] = {}
        for name in active_user_names:
            facts = await self.memory_service.get_quick_facts(user_name=name, chat_id=chat_id)
            if facts:
                quick_facts[name] = facts

        # 3. Get Level 2 deep search using recent conversation as query
        query_lines = [f"{msg.display_name}: {msg.text}" for msg in context[-5:]] if context else []
        query_text = "\n".join(query_lines)
        deep_facts: list[MemoryFact] = []
        if query_text:
            deep_facts = await self.memory_service.search_memories(
                query=query_text, chat_id=chat_id
            )

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

            # 7. Record token usage
            await self.token_repo.record_usage(token_usage)

            return response_text
        except Exception as e:
            logger.error("Error generating LLM response", exc_info=e, chat_id=chat_id)
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
