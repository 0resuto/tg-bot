"""OpenAI LLM provider implementation."""

from __future__ import annotations

from typing import Any

import openai
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from bot.log import get_logger
from bot.models import EmptyLLMResponseError, LLMProvider

logger = get_logger(__name__)


class OpenAILLMProvider(LLMProvider):
    """OpenAI implementation of the LLMProvider protocol."""

    def __init__(
        self,
        api_key: str,
        default_model: str,
        timeout: float = 60.0,
    ):
        self.client = openai.AsyncOpenAI(api_key=api_key, timeout=timeout)
        self.default_model = default_model
        self.timeout = timeout

    async def close(self) -> None:
        """Close underlying AsyncOpenAI HTTP transport pool."""
        await self.client.close()

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type(
            (
                openai.RateLimitError,
                openai.APIConnectionError,
                openai.InternalServerError,
                openai.APITimeoutError,
            )
        ),
        reraise=True,
    )
    async def _call_api(self, **kwargs: Any) -> Any:
        """Execute a single OpenAI API call with retry protection."""
        return await self.client.chat.completions.create(**kwargs)

    async def generate_response(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        max_tokens: int = 1000,
    ) -> str:
        """Generate response using OpenAI API."""
        target_model = model or self.default_model
        api_messages = [{"role": "system", "content": system_prompt}] + messages

        response = await self._call_api(
            model=target_model,
            messages=api_messages,
            max_completion_tokens=max_tokens,
        )

        if not response.choices:
            raise EmptyLLMResponseError(f"LLM returned no choices (model={target_model})")

        choice = response.choices[0]
        content = (choice.message.content or "").strip()
        if not content:
            finish_reason = getattr(choice, "finish_reason", None)
            usage = getattr(response, "usage", None)
            completion_tokens = getattr(usage, "completion_tokens", None) if usage else None
            raise EmptyLLMResponseError(
                "LLM returned an empty response "
                f"(model={target_model}, finish_reason={finish_reason}, "
                f"completion_tokens={completion_tokens}, max_tokens={max_tokens}); "
                "the completion token budget may have been exhausted"
            )

        if getattr(choice, "finish_reason", None) == "length":
            logger.warning(
                "LLM response was truncated by the token limit",
                model=target_model,
                max_tokens=max_tokens,
            )

        return content
