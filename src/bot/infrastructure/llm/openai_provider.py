"""OpenAI LLM provider implementation."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import openai
import structlog
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from bot.domain.enums import OperationType
from bot.domain.models import TokenUsageRecord
from bot.interfaces import LLMProvider

logger = structlog.get_logger()


class OpenAILLMProvider(LLMProvider):
    """OpenAI implementation of the LLMProvider protocol."""

    def __init__(self, api_key: str, default_model: str, default_chat_id: int = 0):
        self.client = openai.AsyncOpenAI(api_key=api_key)
        self.default_model = default_model
        self.default_chat_id = default_chat_id

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type(
            (
                openai.RateLimitError,
                openai.APIConnectionError,
                openai.InternalServerError,
            )
        ),
        reraise=True,
    )
    async def generate_response(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> tuple[str, TokenUsageRecord]:
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
            response = await self.client.chat.completions.create(**kwargs)
        except openai.BadRequestError as err:
            err_msg = str(err)
            if "max_tokens" in err_msg and "max_completion_tokens" in err_msg:
                kwargs.pop("max_tokens", None)
                kwargs["max_completion_tokens"] = max_tokens
                if "temperature" in err_msg:
                    kwargs.pop("temperature", None)
                response = await self.client.chat.completions.create(**kwargs)
            elif "temperature" in err_msg and (
                "unsupported" in err_msg.lower() or "does not support" in err_msg.lower()
            ):
                kwargs.pop("temperature", None)
                response = await self.client.chat.completions.create(**kwargs)
            else:
                raise

        content = response.choices[0].message.content or ""
        usage = response.usage

        prompt_tokens = usage.prompt_tokens if usage else 0
        completion_tokens = usage.completion_tokens if usage else 0
        total_tokens = usage.total_tokens if usage else 0

        record = TokenUsageRecord(
            chat_id=self.default_chat_id,
            model=target_model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            operation=OperationType.RESPONSE,
            telegram_user_id=None,
            timestamp=datetime.now(UTC),
        )

        logger.info(
            "openai_usage",
            model=target_model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )

        return content, record
