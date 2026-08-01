"""
Performance monitoring and metrics collection
"""

import time
import asyncio
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from loguru import logger


@dataclass
class RequestMetrics:
    """Metrics for a single request"""
    timestamp: datetime
    method: str
    path: str
    status_code: int
    duration_ms: float
    session_id: Optional[str] = None
    error: Optional[str] = None


@dataclass
class SystemMetrics:
    """System-wide metrics"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    avg_response_time_ms: float = 0.0
    active_sessions: int = 0
    recent_requests: List[RequestMetrics] = field(default_factory=list)
    
    def add_request(self, metrics: RequestMetrics):
        """Add request metrics"""
        self.total_requests += 1
        
        if 200 <= metrics.status_code < 400:
            self.successful_requests += 1
        else:
            self.failed_requests += 1
        
        # Keep only recent requests (last 1000)
        self.recent_requests.append(metrics)
        if len(self.recent_requests) > 1000:
            self.recent_requests.pop(0)
        
        # Update average response time
        recent_times = [r.duration_ms for r in self.recent_requests[-100:]]
        self.avg_response_time_ms = sum(recent_times) / len(recent_times)
    
    def get_stats(self, window_minutes: int = 60) -> Dict:
        """Get statistics for the specified time window"""
        cutoff_time = datetime.now() - timedelta(minutes=window_minutes)
        recent = [r for r in self.recent_requests if r.timestamp > cutoff_time]
        
        if not recent:
            return {
                "window_minutes": window_minutes,
                "total_requests": 0,
                "successful_requests": 0,
                "failed_requests": 0,
                "avg_response_time_ms": 0.0,
                "error_rate": 0.0
            }
        
        successful = sum(1 for r in recent if 200 <= r.status_code < 400)
        failed = len(recent) - successful
        avg_time = sum(r.duration_ms for r in recent) / len(recent)
        error_rate = (failed / len(recent)) * 100 if recent else 0
        
        return {
            "window_minutes": window_minutes,
            "total_requests": len(recent),
            "successful_requests": successful,
            "failed_requests": failed,
            "avg_response_time_ms": round(avg_time, 2),
            "error_rate": round(error_rate, 2)
        }


# Global metrics instance
_system_metrics = SystemMetrics()


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware to collect request metrics"""
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # Extract session ID if available
        session_id = None
        if request.method == "POST" and "chat" in request.url.path:
            try:
                body = await request.body()
                # Reset body for downstream processing
                async def receive():
                    return {"type": "http.request", "body": body}
                request._receive = receive
                
                # Try to extract session_id from JSON body
                import json
                try:
                    data = json.loads(body.decode())
                    session_id = data.get("session_id")
                except:
                    pass
            except:
                pass
        
        # Process request
        response = await call_next(request)
        
        # Calculate duration
        duration_ms = (time.time() - start_time) * 1000
        
        # Create metrics
        metrics = RequestMetrics(
            timestamp=datetime.now(),
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
            session_id=session_id
        )
        
        # Add to system metrics
        _system_metrics.add_request(metrics)
        
        # Log slow requests
        if duration_ms > 5000:  # 5 seconds
            logger.warning(
                f"Slow request: {request.method} {request.url.path} "
                f"took {duration_ms:.2f}ms (session: {session_id})"
            )
        
        # Add performance headers
        response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"
        
        return response


def get_system_metrics() -> SystemMetrics:
    """Get current system metrics"""
    return _system_metrics


def get_performance_stats(window_minutes: int = 60) -> Dict:
    """Get performance statistics"""
    return _system_metrics.get_stats(window_minutes)


class PerformanceTracker:
    """Context manager for tracking operation performance"""
    
    def __init__(self, operation_name: str, session_id: Optional[str] = None):
        self.operation_name = operation_name
        self.session_id = session_id
        self.start_time = None
        self.end_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.time()
        duration_ms = (self.end_time - self.start_time) * 1000
        
        # Log performance
        log_msg = f"Operation '{self.operation_name}' took {duration_ms:.2f}ms"
        if self.session_id:
            log_msg += f" (session: {self.session_id})"
        
        if duration_ms > 1000:  # Log if > 1 second
            logger.warning(log_msg)
        else:
            logger.debug(log_msg)
        
        # Log errors
        if exc_type:
            logger.error(f"Operation '{self.operation_name}' failed: {exc_val}")


# Async version of performance tracker
class AsyncPerformanceTracker:
    """Async context manager for tracking operation performance"""
    
    def __init__(self, operation_name: str, session_id: Optional[str] = None):
        self.operation_name = operation_name
        self.session_id = session_id
        self.start_time = None
        self.end_time = None
    
    async def __aenter__(self):
        self.start_time = time.time()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.time()
        duration_ms = (self.end_time - self.start_time) * 1000
        
        # Log performance
        log_msg = f"Async operation '{self.operation_name}' took {duration_ms:.2f}ms"
        if self.session_id:
            log_msg += f" (session: {self.session_id})"
        
        if duration_ms > 1000:  # Log if > 1 second
            logger.warning(log_msg)
        else:
            logger.debug(log_msg)
        
        # Log errors
        if exc_type:
            logger.error(f"Async operation '{self.operation_name}' failed: {exc_val}")


# Decorator for tracking function performance
def track_performance(operation_name: str = None):
    """Decorator to track function performance"""
    def decorator(func):
        name = operation_name or f"{func.__module__}.{func.__name__}"
        
        if asyncio.iscoroutinefunction(func):
            async def async_wrapper(*args, **kwargs):
                async with AsyncPerformanceTracker(name):
                    return await func(*args, **kwargs)
            return async_wrapper
        else:
            def sync_wrapper(*args, **kwargs):
                with PerformanceTracker(name):
                    return func(*args, **kwargs)
            return sync_wrapper
    
    return decorator


# Memory usage tracking
def get_memory_usage() -> Dict:
    """Get current memory usage statistics"""
    try:
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        
        return {
            "rss_mb": round(memory_info.rss / 1024 / 1024, 2),
            "vms_mb": round(memory_info.vms / 1024 / 1024, 2),
            "percent": round(process.memory_percent(), 2)
        }
    except ImportError:
        return {"error": "psutil not installed"}
    except Exception as e:
        return {"error": str(e)}


# CPU usage tracking
def get_cpu_usage() -> Dict:
    """Get current CPU usage statistics"""
    try:
        import psutil
        
        return {
            "percent": psutil.cpu_percent(interval=1),
            "count": psutil.cpu_count()
        }
    except ImportError:
        return {"error": "psutil not installed"}
    except Exception as e:
        return {"error": str(e)}