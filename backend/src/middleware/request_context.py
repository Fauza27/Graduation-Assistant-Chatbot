"""Expose stable request and trace identifiers without logging request bodies."""

from __future__ import annotations

import uuid

from starlette.middleware.base import BaseHTTPMiddleware

from src.monitoring.tracing import current_trace_id


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        trace_id = current_trace_id()
        if trace_id:
            response.headers["X-Trace-ID"] = trace_id
        return response
