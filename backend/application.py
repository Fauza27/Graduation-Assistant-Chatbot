from contextlib import asynccontextmanager

from loguru import logger

from slowapi import Limiter
from slowapi.util import get_remote_address

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from telegram import Update

from config.settings import get_settings
from src.bot.application import create_bot, post_init
from src.api import ai
from src.api import health as health_router
from src.api import auth
from src.api import sessions

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    # Pre-warm AI models in the background (or synchronously during startup)
    from src.services.ai_services import preload_models
    preload_models()

    if settings.TELEGRAM_WEBHOOK_URL:
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
    
    yield

    if hasattr(app.state, "bot_app"):
        try:
            await app.state.bot_app.stop()
            await app.state.bot_app.shutdown()
        except Exception:
            logger.exception("Error shutting down Telegram bot")

def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.VERSION,
        description="chatbot assistan yang mampu menjawab pertanyaan terkai kkp/pi",
        docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
        redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
        lifespan=lifespan,
    )

    limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])
    
    app.state.limiter = limiter

    _register_middleware(app, settings)
    _register_routers(app)

    return app

def _register_middleware(app: FastAPI, settings):
    app.add_middleware(SlowAPIMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://localhost:3001", "http://127.0.0.1:3000", "http://127.0.0.1:3001"],
        allow_origin_regex=r"https://.*\.vercel\.app",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

def _register_routers(app: FastAPI):
    API_PREFIX = "/api"

    app.include_router(ai.router, prefix=API_PREFIX)
    app.include_router(auth.router, prefix=API_PREFIX)
    app.include_router(sessions.router, prefix=API_PREFIX)
    app.include_router(health_router.router)


    @app.post(
        "/api/telegram/webhook",
        tags=["Telegram"],
        summary="Telegram webhook receiver",
        include_in_schema=False,
    )
    async def telegram_webhook(request: Request):
        settings = get_settings()

        if settings.TELEGRAM_WEBHOOK_SECRET:
            incoming_token = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
            if incoming_token != settings.TELEGRAM_WEBHOOK_SECRET:
                raise HTTPException(status_code=403, detail="Invalid secret token")

        if not hasattr(request.app.state, "bot_app"):
            raise HTTPException(status_code=503, detail="Bot not initialized")

        data = await request.json()
        bot_app = request.app.state.bot_app
        update = Update.de_json(data=data, bot=bot_app.bot)
        await bot_app.process_update(update)

        return JSONResponse(content={"ok": True})


    @app.get("/")
    async def root():
        settings = get_settings()
        return {
            "message": f"Welcome to {settings.APP_NAME}",
            "version": settings.VERSION,
            "docs": "/docs"
        }