"""Bound expensive AI work by queue time, concurrency, and a deadline."""

from __future__ import annotations

import asyncio
import contextvars
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from typing import Callable, TypeVar

from config.settings import get_settings
from src.monitoring.errors import RequestDeadlineExceeded, ServiceBusyError

T = TypeVar("T")


class AIRequestGuard:
    """Own a bounded executor and avoid an unbounded queue of costly AI calls."""

    def __init__(self, max_concurrency: int, queue_timeout: float, deadline: float):
        self._slots = asyncio.Semaphore(max_concurrency)
        self._executor = ThreadPoolExecutor(
            max_workers=max_concurrency,
            thread_name_prefix="ai-request",
        )
        self._queue_timeout = queue_timeout
        self._deadline = deadline

    async def run(self, operation: Callable[..., T], *args, **kwargs) -> T:
        try:
            await asyncio.wait_for(
                self._slots.acquire(),
                timeout=self._queue_timeout,
            )
        except asyncio.TimeoutError as exc:
            raise ServiceBusyError("Kapasitas pemrosesan AI sedang penuh") from exc

        loop = asyncio.get_running_loop()
        context = contextvars.copy_context()
        future = loop.run_in_executor(
            self._executor,
            lambda: context.run(operation, *args, **kwargs),
        )
        # Slot dilepas saat thread benar-benar selesai. Jika response timeout,
        # pekerjaan yang tidak dapat dibatalkan tidak membuka slot secara dini.
        future.add_done_callback(lambda _: self._slots.release())

        try:
            return await asyncio.wait_for(
                asyncio.shield(future),
                timeout=self._deadline,
            )
        except asyncio.TimeoutError as exc:
            raise RequestDeadlineExceeded(
                f"Pemrosesan melewati batas {self._deadline:g} detik"
            ) from exc

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)


@lru_cache(maxsize=1)
def get_ai_request_guard() -> AIRequestGuard:
    settings = get_settings()
    return AIRequestGuard(
        max_concurrency=settings.MAX_CONCURRENT_REQUESTS,
        queue_timeout=settings.REQUEST_QUEUE_TIMEOUT,
        deadline=settings.REQUEST_TIMEOUT,
    )


def shutdown_ai_request_guard() -> None:
    if get_ai_request_guard.cache_info().currsize:
        get_ai_request_guard().shutdown()
        get_ai_request_guard.cache_clear()
