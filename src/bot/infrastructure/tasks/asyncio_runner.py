"""Background task runner implementation using asyncio."""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import Any

from bot.log import get_logger

logger = get_logger(__name__)


class AsyncioTaskRunner:
    """Background task runner backed by plain ``asyncio.create_task``."""

    def __init__(self) -> None:
        self._tasks: set[asyncio.Task[Any]] = set()

    def schedule(
        self,
        coro: Coroutine[Any, Any, Any],
        *,
        name: str | None = None,
    ) -> None:
        """Schedule a coroutine to run in the background."""
        task = asyncio.create_task(coro, name=name)
        self._tasks.add(task)
        task.add_done_callback(self._on_task_done)

    def _on_task_done(self, task: asyncio.Task[Any]) -> None:
        self._tasks.discard(task)
        if task.cancelled():
            logger.debug("background_task_cancelled", task_name=task.get_name())
            return
        exc = task.exception()
        if exc is not None:
            logger.error(
                "background_task_failed",
                task_name=task.get_name(),
                error=str(exc),
                exc_info=exc,
            )

    async def shutdown(self) -> None:
        """Cancel all pending tasks and wait for them to finish."""
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
