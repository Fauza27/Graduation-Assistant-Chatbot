"""
Rate limiting service khusus untuk admin authentication.

WARNING: Implementasi in-memory dengan TTL untuk mencegah brute-force attacks
pada admin login endpoints. 

MULTI-INSTANCE DEPLOYMENT ISSUE:
- Limit efektif jadi limit × jumlah worker/instance
- Untuk production multi-instance, pertimbangkan Redis-backed rate limiter
- Atau gunakan sticky session/load balancer affinity

Berbeda dari quota mahasiswa yang berbasis daily limit, ini menggunakan 
sliding window untuk deteksi abuse cepat.
"""

import time
import threading
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict

from loguru import logger


@dataclass
class LoginAttempt:
    """Record satu percobaan login"""
    timestamp: float
    success: bool
    ip_address: str


class AdminRateLimiter:
    """
    Rate limiter untuk admin login dengan sliding window approach.
    
    Features:
    - Per-username rate limiting
    - Per-IP rate limiting  
    - Exponential backoff untuk repeated failures
    - Thread-safe operations
    """
    
    def __init__(
        self,
        max_attempts_per_username: int = 5,
        max_attempts_per_ip: int = 10,
        window_seconds: int = 900,  # 15 minutes
        lockout_duration: int = 1800,  # 30 minutes
    ):
        self.max_attempts_per_username = max_attempts_per_username
        self.max_attempts_per_ip = max_attempts_per_ip
        self.window_seconds = window_seconds
        self.lockout_duration = lockout_duration
        
        # Thread-safe storage
        self._username_attempts: Dict[str, list[LoginAttempt]] = defaultdict(list)
        self._ip_attempts: Dict[str, list[LoginAttempt]] = defaultdict(list)
        self._lockouts: Dict[str, float] = {}  # username/ip -> lockout_until_timestamp
        self._lock = threading.RLock()
        
        logger.info(
            "Admin rate limiter initialized: "
            f"{max_attempts_per_username} attempts per username, "
            f"{max_attempts_per_ip} per IP, "
            f"{window_seconds}s window, "
            f"{lockout_duration}s lockout"
        )
    
    def is_allowed(self, username: str, ip_address: str) -> tuple[bool, str]:
        """
        Check if login attempt is allowed.
        
        Returns:
            (is_allowed, reason_if_blocked)
        """
        now = time.time()
        
        with self._lock:
            # Clean expired data
            self._cleanup_expired_attempts(now)
            
            # Check active lockouts
            username_locked_until = self._lockouts.get(f"user:{username}", 0)
            ip_locked_until = self._lockouts.get(f"ip:{ip_address}", 0)
            
            if now < username_locked_until:
                remaining = int(username_locked_until - now)
                return False, f"Username '{username}' locked for {remaining} more seconds"
            
            if now < ip_locked_until:
                remaining = int(ip_locked_until - now)
                return False, f"IP address locked for {remaining} more seconds"
            
            # Count recent attempts
            username_recent_attempts = len([
                attempt for attempt in self._username_attempts[username]
                if now - attempt.timestamp <= self.window_seconds and not attempt.success
            ])
            
            ip_recent_attempts = len([
                attempt for attempt in self._ip_attempts[ip_address]
                if now - attempt.timestamp <= self.window_seconds and not attempt.success
            ])
            
            # Check limits
            if username_recent_attempts >= self.max_attempts_per_username:
                return False, f"Too many failed attempts for username '{username}'"
            
            if ip_recent_attempts >= self.max_attempts_per_ip:
                return False, f"Too many failed attempts from IP {ip_address}"
            
            return True, ""
    
    def record_attempt(
        self, 
        username: str, 
        ip_address: str, 
        success: bool
    ) -> None:
        """
        Record login attempt and apply lockouts if necessary.
        """
        now = time.time()
        attempt = LoginAttempt(
            timestamp=now,
            success=success,
            ip_address=ip_address
        )
        
        with self._lock:
            # Record attempt
            self._username_attempts[username].append(attempt)
            self._ip_attempts[ip_address].append(attempt)
            
            if success:
                # Clear failed attempts on successful login
                self._username_attempts[username] = [
                    a for a in self._username_attempts[username] if a.success
                ]
                # Remove any existing lockouts
                self._lockouts.pop(f"user:{username}", None)
                self._lockouts.pop(f"ip:{ip_address}", None)
                
                logger.info(f"Admin login successful: {username} from {ip_address}")
            else:
                # Count consecutive failures for potential lockout
                username_failures = len([
                    a for a in self._username_attempts[username]
                    if now - a.timestamp <= self.window_seconds and not a.success
                ])
                
                ip_failures = len([
                    a for a in self._ip_attempts[ip_address]
                    if now - a.timestamp <= self.window_seconds and not a.success
                ])
                
                # Apply lockouts if thresholds exceeded
                if username_failures >= self.max_attempts_per_username:
                    self._lockouts[f"user:{username}"] = now + self.lockout_duration
                    logger.warning(
                        f"Admin username '{username}' locked for {self.lockout_duration}s "
                        f"due to {username_failures} failed attempts"
                    )
                
                if ip_failures >= self.max_attempts_per_ip:
                    self._lockouts[f"ip:{ip_address}"] = now + self.lockout_duration
                    logger.warning(
                        f"IP {ip_address} locked for {self.lockout_duration}s "
                        f"due to {ip_failures} failed attempts"
                    )
                
                logger.warning(
                    f"Admin login failed: {username} from {ip_address} "
                    f"(attempt {username_failures}/{self.max_attempts_per_username})"
                )
    
    def _cleanup_expired_attempts(self, now: float) -> None:
        """Remove old attempts and expired lockouts."""
        cutoff = now - self.window_seconds
        
        # Clean old attempts
        for username in list(self._username_attempts.keys()):
            self._username_attempts[username] = [
                attempt for attempt in self._username_attempts[username]
                if attempt.timestamp > cutoff
            ]
            if not self._username_attempts[username]:
                del self._username_attempts[username]
        
        for ip_address in list(self._ip_attempts.keys()):
            self._ip_attempts[ip_address] = [
                attempt for attempt in self._ip_attempts[ip_address]
                if attempt.timestamp > cutoff
            ]
            if not self._ip_attempts[ip_address]:
                del self._ip_attempts[ip_address]
        
        # Clean expired lockouts
        expired_lockouts = [
            key for key, lockout_until in self._lockouts.items()
            if now >= lockout_until
        ]
        for key in expired_lockouts:
            del self._lockouts[key]
    
    def get_stats(self) -> Dict[str, any]:
        """Get current rate limiter statistics."""
        now = time.time()
        
        with self._lock:
            self._cleanup_expired_attempts(now)
            
            active_lockouts = {
                key: int(lockout_until - now)
                for key, lockout_until in self._lockouts.items()
                if now < lockout_until
            }
            
            return {
                "active_lockouts": active_lockouts,
                "tracked_usernames": len(self._username_attempts),
                "tracked_ips": len(self._ip_attempts),
                "total_recent_attempts": sum(
                    len(attempts) for attempts in self._username_attempts.values()
                ),
            }


# Global instance
_admin_rate_limiter = AdminRateLimiter()


def extract_client_ip(request) -> str:
    """
    Extract client IP with proxy support.
    
    For security, X-Forwarded-For header is only trusted when the request 
    comes from a configured trusted proxy. Otherwise, attackers could bypass
    rate limiting by sending fake X-Forwarded-For headers.
    """
    from config.settings import get_settings
    
    # Get direct connection IP first
    direct_ip = getattr(request.client, 'host', 'unknown')
    
    # Only trust X-Forwarded-For from configured trusted proxies
    settings = get_settings()
    trusted_proxies = getattr(settings, 'TRUSTED_PROXIES', ['127.0.0.1', '::1'])
    
    if direct_ip in trusted_proxies:
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Take first IP in chain (original client)
            client_ip = forwarded_for.split(",")[0].strip()
            logger.debug(f"Using X-Forwarded-For IP from trusted proxy: {client_ip}")
            return client_ip
    
    # Use direct IP (either no proxy or untrusted proxy)
    logger.debug(f"Using direct client IP: {direct_ip}")
    return direct_ip


def check_admin_login_allowed(username: str, request) -> tuple[bool, str]:
    """
    Check if admin login attempt is allowed.
    
    Returns:
        (is_allowed, reason_if_blocked)
    """
    ip_address = extract_client_ip(request)
    return _admin_rate_limiter.is_allowed(username, ip_address)


def record_admin_login_attempt(username: str, request, success: bool) -> None:
    """Record admin login attempt with proper IP extraction."""
    ip_address = extract_client_ip(request)
    _admin_rate_limiter.record_attempt(username, ip_address, success)


def get_admin_rate_limiter_stats() -> Dict[str, any]:
    """Get admin rate limiter statistics."""
    return _admin_rate_limiter.get_stats()