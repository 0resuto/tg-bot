from __future__ import annotations

import asyncio

import pytest

from bot.infrastructure.tasks import AsyncioTaskRunner


@pytest.mark.asyncio
async def test_task_runner_schedule_success():
    runner = AsyncioTaskRunner()
    executed = False

    async def sample_job():
        nonlocal executed
        executed = True

    runner.schedule(sample_job(), name="sample_job")
    # Yield control to event loop so task runs
    await asyncio.sleep(0.01)

    assert executed is True
    assert len(runner._tasks) == 0


@pytest.mark.asyncio
async def test_task_runner_handles_exception_safely():
    runner = AsyncioTaskRunner()

    async def failing_job():
        raise RuntimeError("Job failed as expected")

    runner.schedule(failing_job(), name="failing_job")
    await asyncio.sleep(0.01)

    # Task should be discarded from runner's tracked set and not crash
    assert len(runner._tasks) == 0


@pytest.mark.asyncio
async def test_task_runner_shutdown_cancels_pending():
    runner = AsyncioTaskRunner()
    started = False
    cancelled = False

    async def long_running_job():
        nonlocal started, cancelled
        started = True
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            cancelled = True
            raise

    runner.schedule(long_running_job(), name="long_job")
    await asyncio.sleep(0.01)
    assert started is True

    await runner.shutdown()

    assert cancelled is True
    assert len(runner._tasks) == 0
