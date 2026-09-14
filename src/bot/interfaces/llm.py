"""Protocol for the LLM provider abstraction.

Services call this protocol instead of the OpenAI client directly, so the
provider can be swapped (e.g. to Anthropic or a local model) via configuration
without touching business logic.
"""

from __future__ import annotations

from typing import Protocol


class LLMProvider(Protocol):
    """Abstract LLM chat-completion provider."""

    async def generate_response(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        """Generate a chat completion.

        Args:
            system_prompt: The system-level instruction.
            messages: Conversation turns as ``{"role": ..., "content": ...}``
                dicts.
            model: Override the default model name.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens in the response.

        Returns:
            The generated response text.
        """
        ...
