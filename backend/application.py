import asyncio
from contextlib import asynccontextmanager, suppress
import hmac
 
from loguru import logger
 
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
 
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from telegram import Update
 
from config.settings import get_settings
from src.bot.application import create_bot, post_init
from src.services.session_strategy import SessionAccessError
from src.api import ai
from src.api import health as health_router
from src.api import auth
from src.api import sessions
from src.api import admin
from src.api import admin_metrics
from src.api import admin_evaluations

API_PREFIX = "/api"
DEFAULT_RATE_LIMIT = "100/minute"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to every response."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        settings = get_settings()
        if settings.ENVIRONMENT == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize runtime dependencies and clean them up during shutdown."""
    settings = get_settings()

    from src.services.ai_services import (
        get_session_store_strategy,
        preload_models,
    )

    get_session_store_strategy()

    if settings.ENVIRONMENT == "production":
        await asyncio.to_thread(preload_models)
    else:
        logger.info("Scheduling AI model warmup in the background")
        app.state.model_preload_task = asyncio.create_task(
            asyncio.to_thread(preload_models),
            name="ai-model-preload",
        )

    await _start_telegram_bot(app, settings)

    yield

    await _stop_model_preload(app)
    await _stop_telegram_bot(app)

    from src.services.request_guard import shutdown_ai_request_guard

    shutdown_ai_request_guard()


async def _start_telegram_bot(app: FastAPI, settings) -> None:
    """Start the Telegram integration only when webhook mode is configured."""
    if not settings.TELEGRAM_WEBHOOK_URL:
        return

    bot_app = create_bot()
    await bot_app.initialize()
    await post_init(bot_app)

    webhook_url = f"{settings.TELEGRAM_WEBHOOK_URL}{settings.TELEGRAM_WEBHOOK_PATH}"
    await bot_app.bot.set_webhook(
        url=webhook_url,
        secret_token=settings.TELEGRAM_WEBHOOK_SECRET or None,
        drop_pending_updates=True,
    )
    await bot_app.start()
    app.state.bot_app = bot_app


async def _stop_model_preload(app: FastAPI) -> None:
    """Cancel unfinished development warmup before the event loop closes."""
    task = getattr(app.state, "model_preload_task", None)
    if task is None or task.done():
        return

    task.cancel()
    with suppress(asyncio.CancelledError):
        await task


async def _stop_telegram_bot(app: FastAPI) -> None:
    """Stop the Telegram integration when it was initialized."""
    if hasattr(app.state, "bot_app"):
        try:
            await app.state.bot_app.stop()
            await app.state.bot_app.shutdown()
        except Exception:
            logger.exception("Error shutting down Telegram bot")

def create_app() -> FastAPI:
    """Buat dan konfigurasikan instance FastAPI."""
    settings = get_settings()
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.VERSION,
        description="Chatbot asisten yang mampu menjawab pertanyaan terkait KKP/PI/Skripsi dan non skripsi",
        docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
        redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
        lifespan=lifespan,
    )
    app.state.limiter = Limiter(key_func=get_remote_address, default_limits=[DEFAULT_RATE_LIMIT])

    _register_middleware(app)
    _register_routers(app)

    from src.monitoring.tracing import configure_telemetry
    configure_telemetry(app)
 
    return app
def _register_middleware(app: FastAPI) -> None:
    """Daftarkan middleware: security headers, rate limiting, dan CORS."""
    app.add_middleware(SecurityHeadersMiddleware)
    from src.middleware.request_context import RequestContextMiddleware
    app.add_middleware(RequestContextMiddleware)

    app.add_exception_handler(SessionAccessError, _session_access_error_handler)
    app.add_middleware(SlowAPIMiddleware)
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    settings = get_settings()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ALLOWED_ORIGINS,
        allow_origin_regex=settings.CORS_ALLOWED_ORIGIN_REGEX,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
def _register_routers(app: FastAPI) -> None:
    """Daftarkan semua router API beserta endpoint webhook Telegram dan root."""
    app.include_router(ai.router, prefix=API_PREFIX)
    app.include_router(auth.router, prefix=API_PREFIX)
    app.include_router(sessions.router, prefix=API_PREFIX)
    app.include_router(admin.router, prefix=API_PREFIX)
    app.include_router(admin_metrics.router, prefix=API_PREFIX)
    app.include_router(admin_evaluations.router, prefix=API_PREFIX)
    app.include_router(health_router.router)

    app.add_api_route(
        "/api/telegram/webhook",
        _telegram_webhook,
        methods=["POST"],
        tags=["Telegram"],
        summary="Telegram webhook receiver",
        include_in_schema=False,
    )
    app.add_api_route("/", _root, methods=["GET"])
async def _telegram_webhook(request: Request):
    """Terima update dari Telegram; verifikasi secret token sebelum diproses."""
    settings = get_settings()

    if not settings.TELEGRAM_WEBHOOK_SECRET:
        logger.critical("TELEGRAM_WEBHOOK_SECRET not configured - rejecting all webhook requests")
        raise HTTPException(status_code=503, detail="Webhook secret not configured")
    incoming_token = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not hmac.compare_digest(incoming_token, settings.TELEGRAM_WEBHOOK_SECRET):
        raise HTTPException(status_code=403, detail="Invalid secret token")
    if not hasattr(request.app.state, "bot_app"):
        raise HTTPException(status_code=503, detail="Bot not initialized")
 
    data = await request.json()
    bot_app = request.app.state.bot_app
    update = Update.de_json(data=data, bot=bot_app.bot)
    await bot_app.process_update(update)
 
    return JSONResponse(content={"ok": True})
 
async def _root():
    """Endpoint root sederhana untuk info aplikasi."""
    settings = get_settings()
    return {
        "message": f"Welcome to {settings.APP_NAME}",
        "version": settings.VERSION,
        "docs": "/docs",
    }
async def _session_access_error_handler(
    request: Request,
    exc: SessionAccessError,
) -> JSONResponse:
    """Terjemahkan SessionAccessError ke HTTP 403."""
    logger.warning(str(exc))
    return JSONResponse(
        status_code=403,
        content={
            "detail": "Akses ditolak: Anda tidak memiliki akses ke sesi ini."
        },
    )
