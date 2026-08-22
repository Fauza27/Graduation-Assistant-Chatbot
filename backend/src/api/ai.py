import unicodedata
import re
from fastapi import APIRouter, HTTPException, Request, Header
from pydantic import BaseModel, Field, validator
from typing import Optional, Literal
from loguru import logger
from datetime import datetime

from src.services.ai_services import chat as chat_service
from src.services.quota_service import check_and_update_quota
from src.auth.jwt_utils import verify_access_token
from src.monitoring.context import new_collector, start_stage, end_stage
from src.monitoring.writer import persist_quota_rejection
from config.settings import get_settings

router = APIRouter(prefix="/ai", tags=["AI Chatbot"])
settings = get_settings()


def sanitize_input(text: str, max_length: int = 1000) -> str:
    """Sanitize user input untuk pertanyaan natural Indonesia.

    Strategi: bukan whitelist karakter ketat, tapi:
    1. Buang control characters (kategori Unicode "Cc") kecuali whitespace
       yang umum (\\t, \\n, \\r).
    2. Normalisasi whitespace berlebih.
    3. Batasi panjang.

    Aman untuk karakter Indonesia/Unicode umum (è, ñ, é, em-dash, smart
    quotes), karena hanya control chars yang dibuang.
    """
    if not text:
        return ""

    text = text[:max_length]

    cleaned_chars = []
    for ch in text:
        if ch in ("\t", "\n", "\r"):
            cleaned_chars.append(ch)
            continue
        if unicodedata.category(ch) == "Cc":
            # Buang control character lain (mis. NULL, BEL, escape codes).
            continue
        cleaned_chars.append(ch)

    text = "".join(cleaned_chars)

    # Normalisasi whitespace berlebih.
    text = " ".join(text.split())

    return text.strip()


def validate_session_id(session_id: str) -> bool:
    """Validate session ID format"""
    if not session_id:
        return False
    
    # Check length (reasonable bounds)
    if len(session_id) < 3 or len(session_id) > 100:
        return False
    
    # Check for valid characters (alphanumeric, underscore, hyphen)
    if not re.match(r'^[a-zA-Z0-9_-]+$', session_id):
        return False
    
    return True

# Schema Request & Response
class ChatRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=500, description="Pertanyaan dari user")
    session_id: str = Field(..., description="ID sesi percakapan unik per user")
    channel: str = Field(default="website", description="Channel pengirim request (website/telegram)")

    @validator('query')
    def sanitize_query(cls, v):
        if not v or not v.strip():
            raise ValueError("Pertanyaan tidak boleh kosong")
        
        sanitized = sanitize_input(v.strip(), max_length=500)
        if not sanitized:
            raise ValueError("Pertanyaan mengandung karakter yang tidak valid")
        
        if len(sanitized) < 3:
            raise ValueError("Pertanyaan terlalu pendek (minimal 3 karakter)")
            
        return sanitized

    @validator('session_id')
    def validate_session_id_field(cls, v):
        if not validate_session_id(v):
            raise ValueError("Format Session ID tidak valid")
        return v


class ChatResponse(BaseModel):
    answer: str
    num_docs: int
    session_id: str
    sources: list[dict] = []
    intent: str | None = None
    confidence: float | None = None
    reasoning: str | None = None


# Route
@router.post(
    "/chat",
    response_model=ChatResponse,   
    summary="Chat with AI Chatbot",
    description="Kirim pertanyaan ke chatbot RAG KKP/PI",
)
async def chat_endpoint(body: ChatRequest, request: Request):
    # G1/G4/G6: `question` diisi di sini, TITIK PALING AWAL yang mungkin —
    # supaya tetap tercatat walau request gagal di validasi/kuota/generation.
    collector = new_collector(session_id=body.session_id, channel=body.channel, question=body.query)
    start_stage("validation")
    try:
        mahasiswa_id = None
        username = "Unknown User"
        
        # TAHAP 1: Cek Channel
        if body.channel == "telegram":
            raise HTTPException(
                status_code=403, 
                detail="Akses chat Telegram murni diproses melalui Webhook internal."
            )
            
        elif body.channel == "website":
            auth_header = request.headers.get("Authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                raise HTTPException(status_code=401, detail="Token Authorization (Bearer) diperlukan")
                
            token = auth_header.split(" ")[1]
            payload = verify_access_token(token)
            
            # Forward compatibility untuk Increment 3
            if payload.get("role") != "mahasiswa":
                raise HTTPException(status_code=403, detail="Akses ditolak: role tidak sesuai")
                
            mahasiswa_id = payload.get("sub")
            username = payload.get("name", "Website User")
            
            if not mahasiswa_id:
                raise HTTPException(status_code=401, detail="Token tidak valid: sub (mahasiswa_id) tidak ditemukan")

        collector.mahasiswa_id = str(mahasiswa_id) if mahasiswa_id else None
        collector.username = username  # G3: siapa yang mengalami error, kalau nanti gagal di bawah
        end_stage()  # menutup "validation" — kuota & chat_service TIDAK dihitung sebagai validation

        # TAHAP 2: Cek Kuota
        if mahasiswa_id:
            quota_allowed = check_and_update_quota(
                user_id=str(mahasiswa_id),
                daily_limit=settings.RATE_LIMIT_REQUESTS
            )
            
            if not quota_allowed:
                persist_quota_rejection(
                    session_id=body.session_id,
                    channel=body.channel,
                    mahasiswa_id=str(mahasiswa_id),
                )
                raise HTTPException(
                    status_code=429, 
                    detail=f"Batas harian mencapai batas. Maksimal {settings.RATE_LIMIT_REQUESTS} pertanyaan per hari."
                )

        # TAHAP 3: Teruskan ke Chat Service
        # (chat_service akan memakai collector yang sudah kita buat di atas
        # via get_current() — lihat Fase 2 — dan yang akan mem-persist +
        # menutup collector ini di akhir.)
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
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Endpoint /chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))