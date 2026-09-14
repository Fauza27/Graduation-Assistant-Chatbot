from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel
from loguru import logger
from supabase import create_client, Client

from config.settings import get_settings
from src.auth.google_oauth import verify_google_id_token
from src.auth.jwt_utils import create_access_token, verify_access_token
from src.auth.refresh_tokens import (
    InvalidRefreshTokenError,
    RefreshTokenService,
    clear_refresh_cookie,
    set_refresh_cookie,
)
from src.security.browser_origin import require_trusted_origin

settings = get_settings()

router = APIRouter(prefix="/auth", tags=["Auth"])

# Reusable Supabase client
supabase: Client = create_client(settings.supabase_url, settings.supabase_service_key)


def validate_user_role(payload: dict, required_role: str) -> None:
    """
    Validate that the JWT payload contains the required role.
    
    Args:
        payload: JWT payload from verify_access_token
        required_role: Required role (e.g., "mahasiswa", "admin")
        
    Raises:
        HTTPException: If role is missing or incorrect
    """
    actual_role = payload.get("role")
    if actual_role != required_role:
        raise HTTPException(
            status_code=403,
            detail=f"Forbidden: {required_role} role required, got {actual_role}"
        )


class GoogleAuthRequest(BaseModel):
    id_token: str

@router.post("/google/verify")
async def verify_google_auth(request: GoogleAuthRequest, response: Response):
    """
    Verify Google id_token, upsert to database, and return JWT token.
    """
    try:
        # 1. Verify token with Google (using id_token)
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
        if settings.ENABLE_REFRESH_TOKENS:
            refresh_token = RefreshTokenService(supabase).issue(payload)
            set_refresh_cookie(response, refresh_token)

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": settings.JWT_EXPIRATION_MINUTES * 60,
            "mahasiswa_id": mahasiswa_id,
            "name": name,
            "avatar": picture
        }

    except ValueError as ve:
        error_message = str(ve)
        
        # Provide specific error messages for email verification
        if "Email not verified" in error_message:
            logger.warning(f"Google OAuth failed - email not verified: {ve}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Email address must be verified by Google before accessing the system. Please check your email and verify your Google account.",
            )
        else:
            logger.warning(f"Google Token Verification Failed: {ve}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Google token",
            )
    except HTTPException:
        # Re-raise HTTPException tanpa wrapping untuk preserve status codes
        raise
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
    
    # Safe token extraction to prevent IndexError
    token = auth_header[len("Bearer "):].strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Empty token"
        )
    
    # This will raise HTTPException if invalid
    payload = verify_access_token(token)
    
    # Use centralized role validation
    validate_user_role(payload, "mahasiswa")
    
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

@router.post("/refresh")
async def refresh_access_token(request: Request, response: Response):
    """Rotate an HttpOnly refresh token and issue a short-lived access token."""
    if not settings.ENABLE_REFRESH_TOKENS:
        raise HTTPException(status_code=503, detail="Refresh token belum diaktifkan")
    require_trusted_origin(request)

    token = request.cookies.get(settings.REFRESH_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Refresh token tidak ditemukan")

    try:
        rotated = RefreshTokenService(supabase).rotate(token)
        if rotated.payload.get("role") != "mahasiswa":
            raise InvalidRefreshTokenError("Refresh token tidak sesuai channel")
    except InvalidRefreshTokenError as exc:
        clear_refresh_cookie(response)
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Refresh token gagal: {}", type(exc).__name__)
        raise HTTPException(status_code=503, detail="Layanan autentikasi tidak tersedia") from exc

    set_refresh_cookie(response, rotated.token)
    return {
        "access_token": create_access_token(rotated.payload),
        "token_type": "bearer",
        "expires_in": settings.JWT_EXPIRATION_MINUTES * 60,
    }


@router.post("/logout")
async def logout(request: Request, response: Response):
    """Revoke the current refresh token and clear its browser cookie."""
    require_trusted_origin(request)
    token = request.cookies.get(settings.REFRESH_COOKIE_NAME)
    if token and settings.ENABLE_REFRESH_TOKENS:
        RefreshTokenService(supabase).revoke(token)
    clear_refresh_cookie(response)
    return {"message": "Logout sukses"}
