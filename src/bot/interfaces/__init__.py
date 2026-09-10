"""Interface contracts (protocols) for injectable dependencies.

Services program against these protocols, not concrete implementations.
This makes the LLM provider, memory backend, and background task runner
mockable in tests and swappable in production.
"""

from bot.interfaces.llm import LLMProvider
from bot.interfaces.memory import MemoryBackend
from bot.interfaces.task_runner import BackgroundTaskRunner

__all__ = [
    "BackgroundTaskRunner",
    "LLMProvider",
    "MemoryBackend",
]
