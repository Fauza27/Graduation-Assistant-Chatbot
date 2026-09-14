from typing import Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Request, Response
from pydantic import BaseModel, Field, field_validator
from supabase import Client

from src.admin.auth import get_current_admin, authenticate_admin, issue_admin_token, ResourceNotFoundError
from src.admin import chunk_editor
from src.admin.chunk_editor import ChunkConflictError
from src.services.admin_quota_service import (
    check_admin_login_allowed, 
    record_admin_login_attempt,
    get_admin_rate_limiter_stats
)
from config.settings import get_settings
from src.auth.refresh_tokens import (
    InvalidRefreshTokenError,
    RefreshTokenService,
    clear_refresh_cookie,
    set_refresh_cookie,
)
from src.security.browser_origin import require_trusted_origin

router = APIRouter(prefix="/admin", tags=["Admin"])

# Models
class AdminLoginRequest(BaseModel):
    username: str
    password: str
    remember_me: bool = False

class AdminLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    admin: dict

class ChunkSaveRequest(BaseModel):
    title: Optional[str] = Field(None, max_length=500, description="Judul chunk (maksimal 500 karakter)")
    pages: Optional[str] = Field(None, max_length=200, description="Halaman dalam format string, contoh: '1,2,3' atau '12-13'")
    content: Optional[str] = Field(None, max_length=50000, description="Konten chunk (maksimal 50000 karakter untuk kompatibilitas embedding model)")

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        if v is not None and len(v.strip()) == 0:
            raise ValueError("Title tidak boleh kosong jika diisi")
        return v.strip() if v else v

    @field_validator("pages")
    @classmethod
    def validate_pages(cls, v: str) -> str:
        if v is not None and len(v.strip()) == 0:
            raise ValueError("Pages tidak boleh kosong jika diisi")
        return v.strip() if v else v

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        if v is not None:
            if len(v.strip()) == 0:
                raise ValueError("Content tidak boleh kosong jika diisi")
            
            # Check token count estimate (rough approximation: 1 token ≈ 4 characters)
            estimated_tokens = len(v) / 4
            if estimated_tokens > 8000:  # Conservative limit for most embedding models
                raise ValueError(
                    f"Content terlalu panjang (~{int(estimated_tokens)} tokens estimasi). "
                    "Maksimal ~8000 tokens untuk kompatibilitas dengan embedding model. "
                    "Pertimbangkan untuk memecah content menjadi beberapa chunk."
                )
        
        return v.strip() if v else v

class ChunkSaveResponse(BaseModel):
    child_id: str
    embedding_status: str
    content_changed: bool
    message: str

class ReembedTriggerResponse(BaseModel):
    log_id: str
    child_id: str
    status: str
    message: str

class ParentInfo(BaseModel):
    parent_id: str
    title: str

class ChunkDetailResponse(BaseModel):
    id: str
    title: str
    pages: Optional[str] = None  # Serialized from TEXT[] to "page1, page2"
    content: str
    embedding_status: str
    reembedded_at: Optional[datetime] = None
    parent: Optional[ParentInfo] = None
    section: Optional[str] = None
    domain: Optional[str] = None
    source: Optional[str] = None

class DeleteResponse(BaseModel):
    deleted: bool = True
    parent_deleted: bool
    message: str

class ChunkEditStatusResponse(BaseModel):
    status: str
    error_message: Optional[str] = None
    edited_at: datetime
    reembedded_at: Optional[datetime] = None


# Dependencies
def get_supabase() -> Client:
    from supabase import create_client
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_service_key)

# Endpoints
@router.post("/login", response_model=AdminLoginResponse)
def login_admin(req: AdminLoginRequest, request: Request, response: Response, supabase: Client = Depends(get_supabase)):
    # Check rate limiting
    allowed, reason = check_admin_login_allowed(req.username, request)
    if not allowed:
        # Record the blocked attempt
        record_admin_login_attempt(req.username, request, success=False)
        raise HTTPException(
            status_code=429, 
            detail=f"Rate limit exceeded: {reason}"
        )
    
    # Attempt authentication
    admin = authenticate_admin(req.username, req.password, supabase)
    
    # Record attempt result
    success = admin is not None
    record_admin_login_attempt(req.username, request, success=success)
    
    if not success:
        raise HTTPException(status_code=401, detail="Invalid username or password")
        
    token = issue_admin_token(admin)
    settings = get_settings()
    if settings.ENABLE_REFRESH_TOKENS:
        refresh_payload = {
            "sub": str(admin["admin_id"]),
            "username": admin["username"],
            "role": "admin",
        }
        set_refresh_cookie(
            response,
            RefreshTokenService(supabase).issue(
                {**refresh_payload, "persistent": req.remember_me}
            ),
            role="admin",
            persistent=req.remember_me,
        )
    return AdminLoginResponse(
        access_token=token,
        expires_in=settings.JWT_EXPIRATION_MINUTES * 60,
        admin=admin,
    )

@router.post("/logout")
def logout_admin(
    request: Request,
    response: Response,
    supabase: Client = Depends(get_supabase),
):
    settings = get_settings()
    require_trusted_origin(request)
    token = request.cookies.get(settings.ADMIN_REFRESH_COOKIE_NAME)
    if token and settings.ENABLE_REFRESH_TOKENS:
        RefreshTokenService(supabase).revoke(token)
    clear_refresh_cookie(response, role="admin")
    return {"message": "Logged out successfully"}


@router.post("/refresh")
def refresh_admin_token(
    request: Request,
    response: Response,
    supabase: Client = Depends(get_supabase),
):
    """Rotate the admin refresh cookie without requiring an access token."""
    settings = get_settings()
    if not settings.ENABLE_REFRESH_TOKENS:
        raise HTTPException(status_code=503, detail="Refresh token belum diaktifkan")
    require_trusted_origin(request)
    token = request.cookies.get(settings.ADMIN_REFRESH_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Refresh token tidak ditemukan")
    try:
        rotated = RefreshTokenService(supabase).rotate(token)
        if rotated.payload.get("role") != "admin":
            raise InvalidRefreshTokenError("Refresh token tidak sesuai channel")
    except InvalidRefreshTokenError as exc:
        clear_refresh_cookie(response, role="admin")
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    set_refresh_cookie(
        response,
        rotated.token,
        role="admin",
        persistent=bool(rotated.payload.get("persistent", True)),
    )
    return {
        "access_token": issue_admin_token(
            {
                "admin_id": rotated.payload["sub"],
                "username": rotated.payload["username"],
            }
        ),
        "token_type": "bearer",
        "expires_in": settings.JWT_EXPIRATION_MINUTES * 60,
    }

@router.get("/documents")
def get_knowledge_tree(admin: dict = Depends(get_current_admin), supabase: Client = Depends(get_supabase)):
    return chunk_editor.list_knowledge_tree(supabase)

@router.get("/chunks/{child_id}", response_model=ChunkDetailResponse)
def get_chunk(child_id: str, admin: dict = Depends(get_current_admin), supabase: Client = Depends(get_supabase)):
    try:
        detail = chunk_editor.get_chunk_detail(child_id, supabase)
        return detail
    except ResourceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.put("/chunks/{child_id}", response_model=ChunkSaveResponse)
def save_chunk(child_id: str, req: ChunkSaveRequest, admin: dict = Depends(get_current_admin), supabase: Client = Depends(get_supabase)):
    if req.title is None and req.pages is None and req.content is None:
        raise HTTPException(status_code=400, detail="At least one field must be provided for update")
        
    try:
        result = chunk_editor.save_chunk(child_id, admin["sub"], supabase, req.title, req.pages, req.content)
        return result
    except ChunkConflictError as ce:
        # Race condition errors - chunk is being processed or concurrent access
        raise HTTPException(status_code=409, detail=str(ce))
    except ValueError as ve:
        # Input validation errors - bad request
        raise HTTPException(status_code=400, detail=str(ve))
    except ResourceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/chunks/{child_id}/reembed", response_model=ReembedTriggerResponse)
def trigger_reembed_chunk(child_id: str, background_tasks: BackgroundTasks, admin: dict = Depends(get_current_admin), supabase: Client = Depends(get_supabase)):
    try:
        result = chunk_editor.trigger_reembed(child_id, admin["sub"], supabase)
        
        background_tasks.add_task(
            chunk_editor.process_chunk_reembed,
            result["log_id"],
            child_id,
            result["new_content"],
            supabase,
        )
        
        return ReembedTriggerResponse(
            log_id=result["log_id"],
            child_id=child_id,
            status="processing",
            message="Proses re-embed berjalan. Cek progres via GET /chunks/{child_id}/edit-status."
        )
    except ChunkConflictError as ce:
        # Handle idempotency errors and other concurrent access conflicts
        raise HTTPException(status_code=409, detail=str(ce))
    except ResourceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.delete("/chunks/{child_id}", response_model=DeleteResponse)
def delete_chunk_endpoint(child_id: str, admin: dict = Depends(get_current_admin), supabase: Client = Depends(get_supabase)):
    try:
        result = chunk_editor.delete_chunk(child_id, supabase)
        parent_deleted = result["parent_deleted"]
        msg = "Chunk berhasil dihapus."
        if parent_deleted:
            msg += " Parent chunk ini ikut terhapus otomatis karena sudah tidak punya child lagi."
            
        return DeleteResponse(parent_deleted=parent_deleted, message=msg)
    except ChunkConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ResourceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/chunks/{child_id}/edit-status", response_model=ChunkEditStatusResponse)
def get_chunk_edit_status(child_id: str, admin: dict = Depends(get_current_admin), supabase: Client = Depends(get_supabase)):
    status_dict = chunk_editor.get_edit_status(child_id, supabase)
    if not status_dict:
        raise HTTPException(status_code=404, detail="No edit history found for this chunk")
        
    return status_dict

@router.get("/rate-limiter-stats")
def get_rate_limiter_stats(admin: dict = Depends(get_current_admin)):
    """Get admin rate limiter statistics (admin-only endpoint for monitoring)."""
    return {
        "rate_limiter": get_admin_rate_limiter_stats(),
        "message": "Current admin authentication rate limiter status"
    }
