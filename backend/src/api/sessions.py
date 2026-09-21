from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from loguru import logger

from src.auth.jwt_utils import verify_access_token
from src.services.ai_services import get_session_store_strategy

router = APIRouter(prefix="/sessions", tags=["Sessions"])


TokenPayload = dict[str, Any]


def get_current_mahasiswa(request: Request) -> TokenPayload:
    """Read and validate the student access token from the request header."""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")

    token = auth_header[len("Bearer "):].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Empty token")

    payload = verify_access_token(token)

    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")

    actual_role = payload.get("role")
    if actual_role != "mahasiswa":
        raise HTTPException(
            status_code=403,
            detail=f"Forbidden: Mahasiswa role required, got {actual_role}"
        )

    return payload


def _mahasiswa_id(payload: TokenPayload) -> str:
    """Extract the authenticated student identifier from a JWT payload."""
    mahasiswa_id = payload.get("sub")
    if not mahasiswa_id:
        raise HTTPException(status_code=400, detail="Invalid token payload")
    return str(mahasiswa_id)


@router.get("/")
def get_sessions(current_user: TokenPayload = Depends(get_current_mahasiswa)):
    """Get all conversation sessions for the current user."""
    mahasiswa_id = _mahasiswa_id(current_user)

    try:
        sessions = get_session_store_strategy().list_sessions_for_user(mahasiswa_id)
        return {"ok": True, "sessions": sessions}

    except Exception as exc:
        logger.exception("Error fetching sessions for user {}", mahasiswa_id)
        raise HTTPException(status_code=500, detail="Failed to fetch sessions") from exc


@router.get("/{session_id}")
def get_session_details(
    session_id: str,
    current_user: TokenPayload = Depends(get_current_mahasiswa),
):
    """Get details of a specific conversation session."""
    mahasiswa_id = _mahasiswa_id(current_user)

    try:
        session_details = get_session_store_strategy().get_session_details_for_user(
            session_id=session_id,
            mahasiswa_id=mahasiswa_id,
        )

        if session_details is None:
            raise HTTPException(
                status_code=404,
                detail="Session not found or forbidden",
            )

        return {"ok": True, **session_details}

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error fetching session {}", session_id)
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch session details",
        ) from exc


@router.delete("/{session_id}")
def delete_session(
    session_id: str,
    current_user: TokenPayload = Depends(get_current_mahasiswa),
):
    """Delete a specific conversation session."""
    mahasiswa_id = _mahasiswa_id(current_user)

    deleted = get_session_store_strategy().delete_session(
        session_id=session_id,
        mahasiswa_id=mahasiswa_id,
    )

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Session not found or forbidden",
        )

    return {"ok": True, "message": "Session deleted successfully"}
