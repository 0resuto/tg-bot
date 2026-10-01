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
from bot.models import LLMProvider

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
        return response.choices[0].message.content or ""
