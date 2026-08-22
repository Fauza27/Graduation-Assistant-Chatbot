"""
HTTP client kustom untuk OpenAI (dipakai ChatOpenAI & OpenAIEmbeddings)
yang menghitung jumlah retry (response 429/5xx) lewat httpx event hook.
"""

from __future__ import annotations

import httpx

from src.monitoring.context import add_retry

_RETRYABLE_STATUS_CODES = (429, 500, 502, 503, 504)


def _on_response(response: httpx.Response) -> None:
    if response.status_code in _RETRYABLE_STATUS_CODES:
        add_retry()


def build_instrumented_http_client() -> httpx.Client:
    """Buat httpx.Client baru dengan event hook penghitung retry terpasang.

    Dipakai sebagai parameter `http_client=` saat membuat instance
    ChatOpenAI / OpenAIEmbeddings di seluruh codebase (lihat Fase 6)."""
    return httpx.Client(event_hooks={"response": [_on_response]})