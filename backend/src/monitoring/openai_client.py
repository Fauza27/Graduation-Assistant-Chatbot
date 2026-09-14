"""
HTTP client kustom untuk OpenAI
(dipakai ChatOpenAI & OpenAIEmbeddings).

Event hook menghitung jumlah response dengan status yang termasuk retryable:
429, 500, 502, 503, 504.

Catatan observability:
`openai_retry_count` merepresentasikan jumlah retryable response yang
diterima, bukan jaminan jumlah retry aktual yang benar-benar dilakukan SDK.
"""

from __future__ import annotations

import httpx

from src.monitoring.context import add_retry


_RETRYABLE_STATUS_CODES = frozenset(
    {
        429,
        500,
        502,
        503,
        504,
    }
)


def _on_response(response: httpx.Response) -> None:
    """Catat setiap response dengan status retryable."""
    if response.status_code in _RETRYABLE_STATUS_CODES:
        add_retry()


def build_instrumented_http_client() -> httpx.Client:
    """
    Buat httpx.Client dengan response event hook.

    Client ini dipakai sebagai parameter `http_client=` saat membuat
    instance ChatOpenAI / OpenAIEmbeddings.
    """
    return httpx.Client(
        event_hooks={
            "response": [_on_response],
        }
    )