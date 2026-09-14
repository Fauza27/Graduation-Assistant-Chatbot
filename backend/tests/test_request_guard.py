import asyncio
import time

import pytest

from src.monitoring.errors import RequestDeadlineExceeded, ServiceBusyError
from src.services.request_guard import AIRequestGuard


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
