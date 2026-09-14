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

from bot.interfaces import LLMProvider
from bot.log import get_logger

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
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> str:
        """Generate response using OpenAI API."""
        target_model = model or self.default_model

        api_messages = [{"role": "system", "content": system_prompt}] + messages

        model_lower = target_model.lower()
        is_reasoning_or_newer = any(k in model_lower for k in ("o1", "o3", "sol", "gpt-5"))

        kwargs: dict[str, Any] = {
            "model": target_model,
            "messages": api_messages,
        }

        if is_reasoning_or_newer:
            kwargs["max_completion_tokens"] = max_tokens
        else:
            kwargs["max_tokens"] = max_tokens
            if temperature is not None:
                kwargs["temperature"] = temperature

        try:
            response = await self._call_api(**kwargs)
        except openai.BadRequestError as err:
            err_msg = str(err)
            if "max_tokens" in err_msg and "max_completion_tokens" in err_msg:
                kwargs.pop("max_tokens", None)
                kwargs["max_completion_tokens"] = max_tokens
                if "temperature" in err_msg:
                    kwargs.pop("temperature", None)
                response = await self._call_api(**kwargs)
            elif "temperature" in err_msg and (
                "unsupported" in err_msg.lower() or "does not support" in err_msg.lower()
            ):
                kwargs.pop("temperature", None)
                response = await self._call_api(**kwargs)
            else:
                raise

        return response.choices[0].message.content or ""
