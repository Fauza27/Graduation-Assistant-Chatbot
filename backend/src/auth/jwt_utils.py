import jwt
import uuid
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, status
from typing import Dict, Any

from config.settings import get_settings

settings = get_settings()

def create_access_token(data: dict) -> str:
    """
    Generate JWT access token for user sessions.
    """
    to_encode = data.copy()
    
    # Set expiration
    issued_at = datetime.now(timezone.utc)
    expire = issued_at + timedelta(minutes=settings.JWT_EXPIRATION_MINUTES)
    to_encode.update(
        {
            "exp": expire,
            "iat": issued_at,
            "jti": str(uuid.uuid4()),
            "type": "access",
        }
    )
    
    # Encode JWT
    encoded_jwt = jwt.encode(
        to_encode, 
        settings.JWT_SECRET_KEY, 
        algorithm=settings.JWT_ALGORITHM
    )
    return encoded_jwt

def verify_access_token(token: str) -> Dict[str, Any]:
    """
    Verify and decode JWT access token.
    Raises HTTPException if invalid or expired.
    """
    try:
        payload = jwt.decode(
            token, 
            settings.JWT_SECRET_KEY, 
            algorithms=[settings.JWT_ALGORITHM],
            leeway=settings.JWT_CLOCK_SKEW_SECONDS,
        )
        if payload.get("type") != "access":
            raise jwt.InvalidTokenError("Unexpected token type")
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
