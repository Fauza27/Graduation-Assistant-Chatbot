"""
Taksonomi error kustom untuk klasifikasi `error_source` di request_metrics.

Dua cara pakai:
1. Raise exception spesifik (ValidationServiceError, dst) di titik yang kita
   kontrol sendiri — paling akurat.
2. Untuk exception yang datang dari library pihak ketiga (openai-python,
   supabase-py, httpx) yang TIDAK kita bungkus manual, pakai
   `classify_exception()` sebagai fallback berbasis nama modul exception.
"""

from __future__ import annotations


class ChatError(Exception):
    """Base exception untuk semua error di alur chat."""
    error_source = "unknown"


class ValidationServiceError(ChatError):
    error_source = "validation"


class OpenAIServiceError(ChatError):
    error_source = "openai"


class SupabaseServiceError(ChatError):
    error_source = "supabase"


class RetrievalError(ChatError):
    """Dipertahankan agar kompatibel dengan RetrievalError yang sudah ada
    di ai_services.py (Fase 2 akan memindahkan definisinya ke sini)."""
    error_source = "supabase"


class RateLimitServiceError(ChatError):
    error_source = "rate_limit"


def classify_exception(exc: Exception) -> tuple[str, str]:
    """
    Kembalikan (error_source, error_type) dari exception APA PUN — baik
    yang sudah dibungkus manual (ChatError dan turunannya) maupun exception
    mentah dari library pihak ketiga yang belum sempat dibungkus.
    """
    if isinstance(exc, ChatError):
        return exc.error_source, type(exc).__name__

    exc_module = type(exc).__module__ or ""

    if "openai" in exc_module:
        return "openai", type(exc).__name__
    if "postgrest" in exc_module or "supabase" in exc_module or "httpx" in exc_module:
        return "supabase", type(exc).__name__
    if isinstance(exc, ValueError):
        return "validation", type(exc).__name__

    return "unknown", type(exc).__name__