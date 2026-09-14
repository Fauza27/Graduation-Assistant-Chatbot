import re
import unicodedata
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from loguru import logger
from pydantic import BaseModel, Field, field_validator

from config.settings import get_settings
from src.auth.jwt_utils import verify_access_token
from src.monitoring.context import (
    RequestMetricsCollector,
    clear_current,
    end_stage,
    new_collector,
    start_stage,
)
from src.monitoring.errors import SessionAccessError, classify_exception
from src.monitoring.writer import persist_metrics, persist_quota_rejection
from src.services.ai_services import chat as chat_service
from src.services.quota_service import check_and_update_quota

router = APIRouter(prefix="/ai", tags=["AI Chatbot"])
settings = get_settings()

# Konstanta validasi & sanitasi
_SESSION_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+\Z")
_DISALLOWED_UNICODE_CATEGORIES = frozenset({"Cc", "Cf"})


def sanitize_input(text: str, max_length: int = 1000) -> str:
    """Sanitize user input untuk pertanyaan natural Indonesia.

    Mempertahankan tab, newline, carriage return, dan teks natural,
    serta menyaring karakter kontrol (Cc) dan format/bidi override (Cf).
    """
    if not isinstance(text, str):
        return ""

    # Fast-path: karakter printable ASCII (32-126) dan whitespace standar (\t, \n, \r)
    # dijamin aman tanpa perlu lookup unicodedata.category.
    cleaned_chars = [
        ch for ch in text
        if (32 <= ord(ch) <= 126 or ch in "\t\n\r")
        or unicodedata.category(ch) not in _DISALLOWED_UNICODE_CATEGORIES
    ]
    text = "".join(cleaned_chars)

    # Normalisasi spasi per baris dan bersihkan whitespace awal/akhir
    lines = [" ".join(line.split()) for line in text.splitlines()]
    text = "\n".join(lines).strip()

    # Truncate dilakukan setelah pembersihan & normalisasi
    return text[:max_length]


def validate_session_id(session_id: str) -> bool:
    """Validate session ID format (alphanumeric, underscore, hyphen, 3-100 karakter)."""
    if not session_id or not (3 <= len(session_id) <= 100):
        return False
    return bool(_SESSION_ID_PATTERN.match(session_id))


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=500, description="Pertanyaan dari user")
    session_id: str = Field(..., description="ID sesi percakapan unik per user")
    channel: Literal["website", "telegram"] = Field(
        default="website", description="Channel pengirim request (website/telegram)"
    )

    @field_validator("query")
    @classmethod
    def sanitize_query(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Pertanyaan tidak boleh kosong")

        sanitized = sanitize_input(v.strip(), max_length=500)
        if not sanitized:
            raise ValueError("Pertanyaan mengandung karakter yang tidak valid")

        if len(sanitized) < 3:
            raise ValueError("Pertanyaan terlalu pendek (minimal 3 karakter)")

        return sanitized

    @field_validator("session_id")
    @classmethod
    def validate_session_id_field(cls, v: str) -> str:
        if not validate_session_id(v):
            raise ValueError("Format Session ID tidak valid")
        return v


class ChatResponse(BaseModel):
    answer: str
    num_docs: int
    session_id: str
    sources: list[dict] = Field(default_factory=list)

    # Legacy fields dari sistem intent-first terdahulu (dipertahankan untuk backward compatibility)
    intent: str | None = Field(default=None, description="Legacy field: bernilai None pada arsitektur Retrieval-First")
    confidence: float | None = Field(default=None, description="Legacy field: bernilai None pada arsitektur Retrieval-First")
    reasoning: str | None = Field(default=None, description="Legacy field: bernilai None pada arsitektur Retrieval-First")

    error: str | None = None


def _authenticate_website_user(request: Request) -> tuple[str, str]:
    """Verifikasi Bearer token dari header Authorization untuk channel website.

    Mengembalikan (mahasiswa_id, username) jika valid; melempar HTTPException
    (401/403) jika token tidak ada, tidak valid, atau role tidak sesuai.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token Authorization (Bearer) diperlukan")

    token = auth_header[len("Bearer "):].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Empty token")
        
    payload = verify_access_token(token)

    # Consistent role validation
    actual_role = payload.get("role")
    if actual_role != "mahasiswa":
        raise HTTPException(
            status_code=403, 
            detail=f"Role mahasiswa diperlukan untuk mengakses AI Chatbot, got {actual_role}"
        )

    mahasiswa_id = payload.get("sub")
    if not mahasiswa_id:
        raise HTTPException(status_code=401, detail="Token tidak valid: sub (mahasiswa_id) tidak ditemukan")

    username = payload.get("username", "Mahasiswa")
    return str(mahasiswa_id), username


def _enforce_daily_quota(body: ChatRequest, mahasiswa_id: str) -> None:
    """Tolak request (429) jika mahasiswa sudah melampaui kuota harian."""
    quota_allowed = check_and_update_quota(
        user_id=mahasiswa_id,
        daily_limit=settings.RATE_LIMIT_REQUESTS
    )

    if not quota_allowed:
        persist_quota_rejection(
            session_id=body.session_id,
            channel=body.channel,
            mahasiswa_id=mahasiswa_id,
        )
        raise HTTPException(
            status_code=429,
            detail=f"Anda telah mencapai batas kuota harian. Maksimal {settings.RATE_LIMIT_REQUESTS} pertanyaan per hari."
        )


def _record_endpoint_error(
    collector: RequestMetricsCollector,
    exc: Exception,
    default_status_code: int = 500,
) -> None:
    """Catat status error ke collector dan simpan metrik jika belum tercatat."""
    if getattr(collector, "_persisted", False):
        return

    if isinstance(exc, HTTPException):
        http_status = exc.status_code
        if http_status == 429:
            collector.status = "quota_rejected"
            collector.error_source = "rate_limit"
        elif http_status == 403:
            collector.status = "error"
            collector.error_source = "channel_restriction"
        elif http_status == 401:
            collector.status = "error"
            collector.error_source = "authentication"
        else:
            collector.status = "error"
            collector.error_source = "validation"
        collector.error_type = "HTTPException"
    else:
        http_status = default_status_code
        error_source, error_type = classify_exception(exc)
        collector.status = "error"
        collector.error_source = error_source
        collector.error_type = error_type

    collector.http_status = http_status
    persist_metrics(collector)


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Chat with AI Chatbot",
    description="Kirim pertanyaan ke chatbot RAG KKP/PI",
)
def chat_endpoint(body: ChatRequest, request: Request):
    collector = new_collector(session_id=body.session_id, channel=body.channel, question=body.query)
    start_stage("validation")
    try:
        mahasiswa_id: str | None = None
        username = "Unknown User"

        if body.channel == "telegram":
            raise HTTPException(
                status_code=403,
                detail="Akses chat Telegram murni diproses melalui Webhook internal."
            )
        elif body.channel == "website":
            mahasiswa_id, username = _authenticate_website_user(request)
        else:
            raise HTTPException(status_code=400, detail="Channel tidak dikenali")

        collector.mahasiswa_id = mahasiswa_id
        collector.username = username
        end_stage()  # menutup "validation" — kuota & chat_service TIDAK dihitung sebagai validation

        # TAHAP 2: Cek Kuota
        if mahasiswa_id:
            _enforce_daily_quota(body, mahasiswa_id)

        # TAHAP 3: Teruskan ke Chat Service
        result = chat_service(
            query=body.query,
            session_id=body.session_id,
            username=username,
            channel=body.channel,
            mahasiswa_id=mahasiswa_id
        )

        return ChatResponse(
            answer=result["answer"],
            num_docs=result["num_docs"],
            session_id=body.session_id,
            sources=result.get("sources", []),
            intent=result.get("intent"),
            confidence=result.get("confidence"),
            reasoning=result.get("reasoning"),
            error=result.get("error"),
        )
    except SessionAccessError as exc:
        # Handler global menerjemahkan error kepemilikan sesi menjadi HTTP 403.
        _record_endpoint_error(collector, exc, default_status_code=403)
        raise
    except HTTPException as exc:
        _record_endpoint_error(collector, exc)
        raise
    except Exception as e:
        logger.error(f"Endpoint /chat error: {e}")
        _record_endpoint_error(collector, e, default_status_code=500)
        raise HTTPException(
            status_code=500,
            detail="Terjadi kesalahan internal. Silakan coba lagi nanti."
        )
    finally:
        clear_current()
