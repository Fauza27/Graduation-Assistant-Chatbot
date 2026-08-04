from fastapi import APIRouter, HTTPException, Request, Header
from pydantic import BaseModel, Field
from typing import Optional, Literal
from loguru import logger
from datetime import datetime

from src.services.ai_services import chat as chat_service
from src.auth.jwt_utils import verify_access_token
from config.settings import get_settings
from supabase import create_client

router = APIRouter(prefix="/ai", tags=["AI Chatbot"])
settings = get_settings()
supabase = create_client(settings.supabase_url, settings.supabase_service_key)

# Schema Request & Response
class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Pertanyaan dari user")
    session_id: str = Field(..., description="ID sesi percakapan unik per user")
    channel: str = Field(default="website", description="Channel pengirim request (website/telegram)")


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

        # TAHAP 2: Cek Kuota
        if mahasiswa_id:
            today = datetime.now().strftime("%Y-%m-%d")
            try:
                response = supabase.rpc(
                    "increment_quota_if_under_limit",
                    {
                        "p_user_id": str(mahasiswa_id),
                        "p_date": today,
                        "p_daily_limit": settings.RATE_LIMIT_REQUESTS,
                    },
                ).execute()
                
                # RPC returns boolean: True = allowed, False = limit reached
                if not bool(response.data):
                    raise HTTPException(
                        status_code=429, 
                        detail=f"Batas harian mencapai batas. Maksimal {settings.RATE_LIMIT_REQUESTS} pertanyaan per hari."
                    )
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error checking quota for user {mahasiswa_id}: {e}")
                # Fail open to not block user on DB issues

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
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Endpoint /chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))