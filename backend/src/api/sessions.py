from fastapi import APIRouter, Depends, HTTPException, Request
from loguru import logger
from typing import Dict, Any, List

from src.auth.jwt_utils import verify_access_token
from src.services.session_store import get_session_store

router = APIRouter(prefix="/sessions", tags=["Sessions"])

def get_current_mahasiswa(request: Request) -> Dict[str, Any]:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")
        
    token = auth_header.split(" ")[1]
    payload = verify_access_token(token)
    
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
        
    if payload.get("role") != "mahasiswa":
        raise HTTPException(status_code=403, detail="Forbidden: Mahasiswa only")
        
    return payload

@router.get("/")
def get_sessions(current_user: dict = Depends(get_current_mahasiswa)):
    """Get all conversation sessions for the current user."""
    mahasiswa_id = current_user.get("mahasiswa_id")
    if not mahasiswa_id:
        raise HTTPException(status_code=400, detail="Invalid token payload")
        
    session_store = get_session_store()
    try:
        result = session_store._supabase.table("conversation_sessions")\
            .select("session_id, last_access, turns")\
            .eq("mahasiswa_id", str(mahasiswa_id))\
            .order("last_access", desc=True)\
            .execute()
            
        sessions = []
        for row in result.data:
            turns = row.get("turns") or []
            # Find the first user message as the title
            title = "Sesi Tanpa Judul"
            for turn in turns:
                if turn.get("role") == "user":
                    content = turn.get("content", "")
                    title = content[:40] + ("..." if len(content) > 40 else "")
                    break
                    
            sessions.append({
                "session_id": row.get("session_id"),
                "title": title,
                "last_access": row.get("last_access")
            })
            
        return {"ok": True, "sessions": sessions}
        
    except Exception as e:
        logger.error(f"Error fetching sessions for user {mahasiswa_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch sessions")

@router.get("/{session_id}")
def get_session_details(session_id: str, current_user: dict = Depends(get_current_mahasiswa)):
    """Get details of a specific conversation session."""
    mahasiswa_id = current_user.get("mahasiswa_id")
    
    session_store = get_session_store()
    try:
        result = session_store._supabase.table("conversation_sessions")\
            .select("turns")\
            .eq("session_id", session_id)\
            .eq("mahasiswa_id", str(mahasiswa_id))\
            .execute()
            
        if not result.data:
            raise HTTPException(status_code=404, detail="Session not found or forbidden")
            
        turns = result.data[0].get("turns") or []
        
        # Format for frontend
        messages = []
        for turn in turns:
            role = turn.get("role")
            if role == "assistant":
                role = "bot"
            
            messages.append({
                "role": role,
                "text": turn.get("content"),
                "sources": turn.get("retrieved_doc_contents", [])
            })
            
        return {"ok": True, "messages": messages}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching session {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch session details")

@router.delete("/{session_id}")
def delete_session(session_id: str, current_user: dict = Depends(get_current_mahasiswa)):
    """Delete a specific conversation session."""
    mahasiswa_id = current_user.get("mahasiswa_id")
    
    session_store = get_session_store()
    try:
        result = session_store._supabase.table("conversation_sessions")\
            .delete()\
            .eq("session_id", session_id)\
            .eq("mahasiswa_id", str(mahasiswa_id))\
            .execute()
            
        # Supabase Python client returns data of deleted rows
        if not result.data:
            raise HTTPException(status_code=404, detail="Session not found or forbidden")
            
        # Clean up from cache just in case it's there
        with session_store._cache_lock:
            session_store._cache.pop(session_id, None)
            session_store._cache_access.pop(session_id, None)
            
        return {"ok": True, "message": "Session deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting session {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete session")
