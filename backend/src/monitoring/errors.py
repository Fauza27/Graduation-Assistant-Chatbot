"""
Taksonomi error kustom untuk klasifikasi `error_source` di request_metrics.

Dua cara pakai:

1. Raise exception spesifik (ValidationServiceError, dst.) di titik yang
   kita kontrol sendiri — paling akurat.

2. Untuk exception dari library pihak ketiga (openai-python, supabase-py,
   httpx) yang belum kita bungkus manual, gunakan classify_exception()
   sebagai fallback berbasis module exception.
"""

from __future__ import annotations


class ChatError(Exception):
    """Base exception untuk semua error di alur chat."""

    error_source = "unknown"


class ValidationServiceError(ChatError):
    """Error yang berkaitan dengan validasi request."""

    error_source = "validation"


class OpenAIServiceError(ChatError):
    """Error yang berasal dari layanan OpenAI."""

    error_source = "openai"


class SupabaseServiceError(ChatError):
    """Error yang berasal dari layanan Supabase/PostgREST."""

    error_source = "supabase"


class RetrievalError(ChatError):
    """
    Error pada retrieval pipeline.

    Retrieval dapat gagal pada beberapa subsistem, misalnya:
    embedding, vector search, BM25, reranker, atau parent fetch.
    """

    error_source = "retrieval"


class ServiceBusyError(ChatError):
    """Request ditolak karena seluruh worker AI sedang digunakan."""

    error_source = "capacity"


class RequestDeadlineExceeded(ChatError, TimeoutError):
    """Batas waktu keseluruhan request telah terlampaui."""

    error_source = "timeout"


class RateLimitServiceError(ChatError):
    """Request ditolak karena rate/quota limit."""

    error_source = "rate_limit"


class SessionAccessError(ChatError):
    """
    Error otorisasi session (IDOR protection).

    Terjadi ketika user mencoba mengakses, memodifikasi, atau menghapus
    session yang dimiliki oleh user lain, atau request tanpa identitas
    mencoba mengakses session yang memiliki pemilik.
    """

    error_source = "security_idor"

    def __init__(
        self,
        session_owner_id: str | None,
        requested_owner_id: str | None,
    ) -> None:
        self.session_owner_id = session_owner_id
        self.requested_owner_id = requested_owner_id
        super().__init__(
            f"IDOR attempt: requested_owner={requested_owner_id} "
            f"tried to access session owned by={session_owner_id}"
        )


class ChannelRestrictionError(ChatError):
    """Error ketika request masuk dari channel yang tidak diizinkan atau dibatasi."""

    error_source = "channel_restriction"


class AuthenticationError(ChatError):
    """Request memerlukan autentikasi tetapi kredensial tidak tersedia atau tidak valid."""

    error_source = "authentication"

    def __init__(self, message: str = "Autentikasi diperlukan.") -> None:
        self.message = message
        super().__init__(message)


def classify_exception(exc: Exception) -> tuple[str, str]:
    """
    Kembalikan (error_source, error_type) dari exception.

    Untuk ChatError, gunakan taxonomy eksplisit dari class.

    Untuk exception pihak ketiga yang belum dibungkus, gunakan module name
    sebagai fallback heuristic.
    """
    if isinstance(exc, ChatError):
        return exc.error_source, type(exc).__name__

    exc_module = type(exc).__module__ or ""
    error_type = type(exc).__name__

    # OpenAI harus diperiksa sebelum fallback generic.
    if "openai" in exc_module:
        return "openai", error_type

    # PostgREST/Supabase harus diperiksa sebelum httpx.
    if "postgrest" in exc_module or "supabase" in exc_module:
        return "supabase", error_type

    # httpx yang tidak bisa dikaitkan secara spesifik dengan service tertentu
    # dikategorikan sebagai network.
    if "httpx" in exc_module:
        return "network", error_type

    if isinstance(exc, ValueError):
        return "validation", error_type

    return "unknown", error_type
