from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from src.services.ai_services import chat as chat_service

router = APIRouter(prefix="/ai", tags=["AI Chatbot"])


# Schema Request & Response
class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Pertanyaan dari user")
    session_id: str = Field(..., description="ID sesi percakapan unik per user")


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
async def chat_endpoint(body: ChatRequest):
    try:
        result = chat_service(
            query=body.query,
            session_id=body.session_id,
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))