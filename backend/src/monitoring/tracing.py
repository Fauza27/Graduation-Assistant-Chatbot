"""OpenTelemetry setup and small safe tracing helpers."""

from __future__ import annotations

import contextlib
import threading
from collections.abc import Iterator
from typing import Any

from loguru import logger

from config.settings import get_settings

_setup_lock = threading.Lock()
_configured = False


def configure_telemetry(app: Any) -> None:
    """Configure FastAPI tracing once when explicitly enabled."""
    global _configured
    settings = get_settings()
    if not settings.OTEL_ENABLED:
        return

    with _setup_lock:
        if _configured:
            _instrument_fastapi(app)
            return

        try:
            from opentelemetry import trace
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor

            provider = TracerProvider(
                resource=Resource.create(
                    {
                        "service.name": settings.OTEL_SERVICE_NAME,
                        "service.version": settings.VERSION,
                        "deployment.environment.name": settings.ENVIRONMENT,
                    }
                )
            )
            if settings.OTEL_EXPORTER_OTLP_ENDPOINT:
                from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                    OTLPSpanExporter,
                )

                headers = _parse_headers(settings.OTEL_EXPORTER_OTLP_HEADERS)
                exporter = OTLPSpanExporter(
                    endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT,
                    headers=headers,
                )
                provider.add_span_processor(BatchSpanProcessor(exporter))
            trace.set_tracer_provider(provider)
            _configured = True
            _instrument_fastapi(app)
            logger.info(
                "OpenTelemetry aktif untuk service {}", settings.OTEL_SERVICE_NAME
            )
        except Exception:
            logger.exception("OpenTelemetry gagal diinisialisasi")
            raise


def _instrument_fastapi(app: Any) -> None:
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    if getattr(app.state, "otel_instrumented", False):
        return
    FastAPIInstrumentor.instrument_app(
        app,
        excluded_urls="health,health/liveness,health/readiness",
    )
    app.state.otel_instrumented = True


def _parse_headers(value: str | None) -> dict[str, str] | None:
    if not value:
        return None
    headers: dict[str, str] = {}
    for item in value.split(","):
        key, separator, raw_value = item.partition("=")
        if separator and key.strip():
            headers[key.strip()] = raw_value.strip()
    return headers or None


@contextlib.contextmanager
def trace_span(name: str, **attributes: Any) -> Iterator[Any]:
    """Create a span when OTel is active; otherwise act as a no-op."""
    if not get_settings().OTEL_ENABLED:
        yield None
        return
    from opentelemetry import trace

    tracer = trace.get_tracer("graduation-assistant")
    clean_attributes = {
        key: value
        for key, value in attributes.items()
        if value is not None and isinstance(value, (str, bool, int, float))
    }
    with tracer.start_as_current_span(name, attributes=clean_attributes) as span:
        yield span


def current_trace_id() -> str | None:
    if not get_settings().OTEL_ENABLED:
        return None
    from opentelemetry import trace

    context = trace.get_current_span().get_span_context()
    if not context.is_valid:
        return None
    return format(context.trace_id, "032x")


def add_current_span_attribute(name: str, value: Any) -> None:
    if not get_settings().OTEL_ENABLED or value is None:
        return
    from opentelemetry import trace

    span = trace.get_current_span()
    if span.is_recording():
        span.set_attribute(name, value)
