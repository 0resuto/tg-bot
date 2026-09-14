"""Protocol for the background task runner abstraction.

The default implementation uses ``asyncio.create_task``.  It can be replaced
with Celery, arq, or any other task runner by implementing this protocol.
"""

from __future__ import annotations

from collections.abc import Coroutine
from typing import Any, Protocol


class BackgroundTaskRunner(Protocol):
    """Abstraction for scheduling fire-and-forget async work."""

    def schedule(
        self,
        coro: Coroutine[Any, Any, Any],
        *,
        name: str | None = None,
    ) -> None:
        """Schedule a coroutine to run in the background.

        Args:
            coro: An *unawaited* coroutine to execute.
            name: Optional human-readable name for logging.
        """
        ...

    async def shutdown(self) -> None:
        """Cancel all pending tasks and wait for them to finish."""
        ...


__all__ = ["BackgroundTaskRunner"]
