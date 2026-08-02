"""
Security middleware and utilities
"""

import time
import hashlib
import hmac
from typing import Dict, Optional, Tuple
from fastapi import Request, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from loguru import logger

from config.settings import get_settings
settings = get_settings()

# Rate limiting storage (in production, use Redis)
_rate_limit_storage: Dict[str, Dict[str, float]] = {}


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware"""
    
    def __init__(self, app, requests_per_window: int = None, window_seconds: int = None):
        super().__init__(app)
        self.requests_per_window = requests_per_window or settings.RATE_LIMIT_REQUESTS
        self.window_seconds = window_seconds or settings.RATE_LIMIT_WINDOW
    
    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health checks
        if request.url.path.startswith("/health"):
            return await call_next(request)
        
        # Get client identifier
        client_id = self._get_client_id(request)
        
        # Check rate limit
        allowed, remaining, reset_time = self._check_rate_limit(client_id)
        
        if not allowed:
            logger.warning(f"Rate limit exceeded for client {client_id}")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": "Rate limit exceeded",
                    "limit": self.requests_per_window,
                    "window_seconds": self.window_seconds,
                    "reset_time": reset_time
                }
            )
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_window)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(int(reset_time))
        response.headers["X-RateLimit-Window"] = str(self.window_seconds)
        
        return response
    
    def _get_client_id(self, request: Request) -> str:
        """Get client identifier for rate limiting"""
        # Try to get user ID from session/auth first
        session_id = getattr(request.state, 'session_id', None)
        if session_id:
            return f"session:{session_id}"
        
        # Fallback to IP address
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "unknown"
        
        return f"ip:{client_ip}"
    
    def _check_rate_limit(self, client_id: str) -> Tuple[bool, int, float]:
        """Check if client is within rate limit"""
        current_time = time.time()
        window_start = current_time - self.window_seconds
        
        # Clean old entries
        if client_id in _rate_limit_storage:
            _rate_limit_storage[client_id] = {
                timestamp: count for timestamp, count in _rate_limit_storage[client_id].items()
                if float(timestamp) > window_start
            }
        else:
            _rate_limit_storage[client_id] = {}
        
        # Count requests in current window
        total_requests = sum(_rate_limit_storage[client_id].values())
        
        # Check if limit exceeded
        if total_requests >= self.requests_per_window:
            reset_time = current_time + self.window_seconds
            return False, 0, reset_time
        
        # Record this request
        timestamp_key = str(current_time)
        _rate_limit_storage[client_id][timestamp_key] = 1
        
        remaining = self.requests_per_window - total_requests - 1
        reset_time = current_time + self.window_seconds
        
        return True, remaining, reset_time


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to responses"""
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Only add HSTS in production with HTTPS
        if settings.is_production():
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        return response


def verify_telegram_webhook(request_body: bytes, signature: str) -> bool:
    """Verify Telegram webhook signature"""
    if not settings.TELEGRAM_WEBHOOK_SECRET:
        logger.warning("Telegram webhook secret not configured")
        return True  # Allow in development
    
    if not signature:
        return False
    
    # Remove 'sha256=' prefix if present
    if signature.startswith('sha256='):
        signature = signature[7:]
    
    # Calculate expected signature
    expected_signature = hmac.new(
        settings.TELEGRAM_WEBHOOK_SECRET.encode(),
        request_body,
        hashlib.sha256
    ).hexdigest()
    
    # Constant-time comparison
    return hmac.compare_digest(signature, expected_signature)


def sanitize_input(text: str, max_length: int = 1000) -> str:
    """Sanitize user input untuk pertanyaan natural Indonesia.

    Strategi: bukan whitelist karakter ketat, tapi:
    1. Buang control characters (kategori Unicode "Cc") kecuali whitespace
       yang umum (\\t, \\n, \\r).
    2. Normalisasi whitespace berlebih.
    3. Batasi panjang.

    Aman untuk karakter Indonesia/Unicode umum (è, ñ, é, em-dash, smart
    quotes), karena hanya control chars yang dibuang.
    """
    if not text:
        return ""

    text = text[:max_length]

    import unicodedata

    cleaned_chars = []
    for ch in text:
        if ch in ("\t", "\n", "\r"):
            cleaned_chars.append(ch)
            continue
        if unicodedata.category(ch) == "Cc":
            # Buang control character lain (mis. NULL, BEL, escape codes).
            continue
        cleaned_chars.append(ch)

    text = "".join(cleaned_chars)

    # Normalisasi whitespace berlebih.
    text = " ".join(text.split())

    return text.strip()


def validate_session_id(session_id: str) -> bool:
    """Validate session ID format"""
    if not session_id:
        return False
    
    # Check length (reasonable bounds)
    if len(session_id) < 3 or len(session_id) > 100:
        return False
    
    # Check for valid characters (alphanumeric, underscore, hyphen)
    import re
    if not re.match(r'^[a-zA-Z0-9_-]+$', session_id):
        return False
    
    return True


class InputValidationError(Exception):
    """Exception for input validation errors"""
    pass


def validate_chat_input(question: str, session_id: str) -> Tuple[str, str]:
    """Validate and sanitize chat input"""
    
    # Validate session ID
    if not validate_session_id(session_id):
        raise InputValidationError("Invalid session ID format")
    
    # Sanitize question
    sanitized_question = sanitize_input(question, max_length=500)
    
    if not sanitized_question:
        raise InputValidationError("Question cannot be empty")
    
    if len(sanitized_question) < 3:
        raise InputValidationError("Question too short")
    
    return sanitized_question, session_id


# Security utility functions
def generate_secure_token(length: int = 32) -> str:
    """Generate cryptographically secure random token"""
    import secrets
    return secrets.token_urlsafe(length)


def hash_sensitive_data(data: str) -> str:
    """Hash sensitive data for logging/storage"""
    return hashlib.sha256(data.encode()).hexdigest()[:16]  # First 16 chars for brevity