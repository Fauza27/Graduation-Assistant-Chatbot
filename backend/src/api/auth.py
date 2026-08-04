from fastapi import APIRouter, Request, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Dict, Any, Optional
from loguru import logger
from supabase import create_client, Client

from config.settings import get_settings
from src.auth.google_oauth import verify_google_id_token
from src.auth.jwt_utils import create_access_token, verify_access_token

settings = get_settings()

router = APIRouter(prefix="/auth", tags=["Auth"])

# Reusable Supabase client
supabase: Client = create_client(settings.supabase_url, settings.supabase_service_key)

class GoogleAuthRequest(BaseModel):
    id_token: str

@router.post("/google/verify")
async def verify_google_auth(request: GoogleAuthRequest):
    """
    Verify Google id_token, upsert to database, and return JWT token.
    """
    try:
        # 1. Verify token with Google
        google_profile = verify_google_id_token(request.id_token)
        google_sub = google_profile.get("sub")
        email = google_profile.get("email")
        name = google_profile.get("name")
        picture = google_profile.get("picture")

        if not google_sub or not email:
            raise HTTPException(status_code=400, detail="Invalid Google profile data")

        # 2. Upsert to Supabase
        # Using atomic upsert via ON CONFLICT DO UPDATE (if table has unique constraint on google_sub)
        upsert_response = supabase.table(settings.table_mahasiswa_accounts).upsert(
            {
                "google_sub": google_sub,
                "email": email,
                "nama": name,
                "avatar_url": picture,
                # last_login will be handled by the database default or trigger, 
                # or we can explicitly set it here if we want:
                # "last_login": "now()"
            },
            on_conflict="google_sub"
        ).execute()

        if not upsert_response.data:
            raise HTTPException(status_code=500, detail="Failed to save user data")

        mahasiswa_id = upsert_response.data[0].get("mahasiswa_id")

        # 3. Create our internal JWT
        payload = {
            "sub": str(mahasiswa_id),
            "name": name,
            "email": email,
            "role": "mahasiswa"
        }
        access_token = create_access_token(payload)

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "mahasiswa_id": mahasiswa_id,
            "name": name,
            "avatar": picture
        }

    except ValueError as ve:
        logger.warning(f"Google Token Verification Failed: {ve}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google token",
        )
    except Exception as e:
        logger.error(f"Error during Google authentication: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during authentication",
        )

@router.get("/me")
async def get_current_user(request: Request):
    """
    Get current logged in user profile using Bearer token.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
        )
    
    token = auth_header.split(" ")[1]
    
    # This will raise HTTPException if invalid
    payload = verify_access_token(token)
    
    mahasiswa_id = payload.get("sub")
    if not mahasiswa_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")
        
    try:
        # Fetch detailed profile from database
        result = supabase.table(settings.table_mahasiswa_accounts).select("*").eq("mahasiswa_id", mahasiswa_id).single().execute()
        return result.data
    except Exception as e:
        logger.error(f"Failed to fetch user profile: {e}")
        # Fallback to token payload
        return {
            "mahasiswa_id": payload.get("sub"),
            "nama": payload.get("name"),
            "email": payload.get("email"),
            "role": payload.get("role")
        }

@router.post("/logout")
async def logout():
    """
    Logout endpoint. Client is responsible for clearing the token.
    """
    return {"message": "Logout sukses"}
