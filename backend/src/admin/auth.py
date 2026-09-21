import bcrypt
from fastapi import Header, HTTPException
from loguru import logger
from supabase import Client

from src.auth.jwt_utils import create_access_token, verify_access_token


class ResourceNotFoundError(Exception):
    """Raised when an admin resource cannot be found."""



def hash_password(plain_password: str) -> str:
    """Hashes a password using bcrypt."""
    salt = bcrypt.gensalt()
    hashed_bytes = bcrypt.hashpw(plain_password.encode('utf-8'), salt)
    return hashed_bytes.decode('utf-8')

def verify_password(plain_password: str, password_hash: str) -> bool:
    """Verifies a password against a hash."""
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), password_hash.encode('utf-8'))
    except ValueError:
        return False

def authenticate_admin(
    username: str,
    plain_password: str,
    supabase: Client,
) -> dict | None:
    """Authenticates an admin and returns their profile without the password hash."""
    response = (
        supabase.table("admin_users")
        .select("*")
        .eq("username", username)
        .limit(1)
        .execute()
    )

    if not response.data:
        return None
        
    admin_data = response.data[0]
    password_hash = admin_data.get("password_hash")
    
    if not password_hash or not verify_password(plain_password, password_hash):
        return None
        
    try:
        (
            supabase.table("admin_users")
            .update({"last_login": "now()"})
            .eq("admin_id", admin_data["admin_id"])
            .execute()
        )
    except Exception as exc:
        logger.warning("Failed to update last_login for admin {}: {}", username, exc)

    return {
        "admin_id": admin_data["admin_id"],
        "username": admin_data["username"],
        "full_name": admin_data.get("full_name"),
    }

def issue_admin_token(admin: dict) -> str:
    """Issues a JWT token for the authenticated admin."""
    payload = {
        "sub": admin["admin_id"],
        "username": admin["username"],
        "role": "admin"
    }
    return create_access_token(payload)

def get_current_admin(authorization: str = Header(None)) -> dict:
    """FastAPI dependency to get the current authenticated admin from the token."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid or missing authorization header")
        
    token = authorization[len("Bearer "):].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Empty token")
        
    payload = verify_access_token(token)
    
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
        
    actual_role = payload.get("role")
    if actual_role != "admin":
        raise HTTPException(
            status_code=403,
            detail=f"Insufficient permissions: admin role required, got {actual_role}",
        )

    return payload
