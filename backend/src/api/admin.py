from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, Field
from supabase import Client

from src.admin.auth import get_current_admin, authenticate_admin, issue_admin_token, ResourceNotFoundError
from src.admin import chunk_editor
from config.settings import get_settings

router = APIRouter(prefix="/admin", tags=["Admin"])

# Models
class AdminLoginRequest(BaseModel):
    username: str
    password: str

class AdminLoginResponse(BaseModel):
    access_token: str
    admin: dict

class ChunkSaveRequest(BaseModel):
    title: Optional[str] = None
    pages: Optional[str] = None  # Frontend sends as string e.g. "12-13"; backend converts to ["12-13"]
    content: Optional[str] = None

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
def login_admin(req: AdminLoginRequest, supabase: Client = Depends(get_supabase)):
    admin = authenticate_admin(req.username, req.password, supabase)
    if not admin:
        raise HTTPException(status_code=401, detail="Invalid username or password")
        
    token = issue_admin_token(admin)
    return AdminLoginResponse(access_token=token, admin=admin)

@router.post("/logout")
def logout_admin(admin: dict = Depends(get_current_admin)):
    # JWT is stateless, so we just return success. Client should delete token.
    return {"message": "Logged out successfully"}

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
    except ResourceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/chunks/{child_id}/reembed", response_model=ReembedTriggerResponse)
def trigger_reembed_chunk(child_id: str, background_tasks: BackgroundTasks, admin: dict = Depends(get_current_admin), supabase: Client = Depends(get_supabase)):
    try:
        result = chunk_editor.trigger_reembed(child_id, admin["sub"], supabase)
        settings = get_settings()
        
        background_tasks.add_task(
            chunk_editor.process_chunk_reembed,
            result["log_id"],
            child_id,
            result["parent_id"],
            result["old_content"],
            result["new_content"],
            supabase,
            settings
        )
        
        return ReembedTriggerResponse(
            log_id=result["log_id"],
            child_id=child_id,
            status="processing",
            message="Proses re-embed berjalan. Cek progres via GET /chunks/{child_id}/edit-status."
        )
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
    except ResourceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/chunks/{child_id}/edit-status", response_model=ChunkEditStatusResponse)
def get_chunk_edit_status(child_id: str, admin: dict = Depends(get_current_admin), supabase: Client = Depends(get_supabase)):
    status_dict = chunk_editor.get_edit_status(child_id, supabase)
    if not status_dict:
        raise HTTPException(status_code=404, detail="No edit history found for this chunk")
        
    return status_dict
