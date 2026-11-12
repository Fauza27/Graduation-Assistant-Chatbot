import asyncio
import time

import pytest

from src.monitoring.errors import RequestDeadlineExceeded, ServiceBusyError
from src.services.request_guard import AIRequestGuard
from src.monitoring.context import new_collector, clear_current


@pytest.mark.asyncio
async def test_guard_rejects_queue_and_keeps_slot_until_timed_out_work_finishes():
    guard = AIRequestGuard(max_concurrency=1, queue_timeout=0.05, deadline=0.05)

    first = asyncio.create_task(guard.run(time.sleep, 0.2))
    await asyncio.sleep(0.01)

    with pytest.raises(ServiceBusyError):
        await guard.run(lambda: "never-started")
    with pytest.raises(RequestDeadlineExceeded):
        await first

    # Thread tetap memegang slot setelah response timeout.
    with pytest.raises(ServiceBusyError):
        await guard.run(lambda: "still-busy")

    await asyncio.sleep(0.16)
    assert await guard.run(lambda: "available") == "available"
    guard.shutdown()


@pytest.mark.asyncio
async def test_timeout_marks_the_shared_collector_before_background_work_finishes():
    guard = AIRequestGuard(max_concurrency=1, queue_timeout=0.05, deadline=0.01)
    collector = new_collector('timeout-test', 'test')
    try:
        with pytest.raises(RequestDeadlineExceeded):
            await guard.run(time.sleep, 0.05)
        assert collector._response_abandoned.is_set()
        await asyncio.sleep(0.06)
    finally:
        clear_current()
        guard.shutdown()
