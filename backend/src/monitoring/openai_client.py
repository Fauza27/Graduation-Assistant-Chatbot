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

from config.settings import get_settings

from src.monitoring.context import add_retry
from src.monitoring.context import set_field
from src.monitoring.tracing import add_current_span_attribute


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
    request_id = response.headers.get("x-request-id")
    if request_id:
        set_field(provider_request_id=request_id)
        add_current_span_attribute("gen_ai.provider.request_id", request_id)


def build_instrumented_http_client() -> httpx.Client:
    """
    Buat httpx.Client dengan response event hook.

    Client ini dipakai sebagai parameter `http_client=` saat membuat
    instance ChatOpenAI / OpenAIEmbeddings.
    """
    settings = get_settings()
    timeout_seconds = min(settings.openai_timeout, settings.REQUEST_TIMEOUT)
    return httpx.Client(
        timeout=httpx.Timeout(timeout_seconds),
        event_hooks={
            "response": [_on_response],
        }
    )
