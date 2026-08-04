import asyncio
import html
from datetime import datetime
from functools import lru_cache
from loguru import logger

from telegram import Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import ContextTypes, MessageHandler, filters
from supabase import create_client, Client

from config.settings import get_settings
from src.bot import messages
from src.retrieval.source_utils import detect_panduan_type
from src.services.ai_services import chat


@lru_cache(maxsize=1)
def _get_supabase_client() -> Client:
    """Reuse single Supabase client instance across requests."""
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_service_key)


def check_and_update_quota(user_id: str) -> bool:
    """
    Atomically increment quota and check daily limit via RPC.

    Returns True if user is still under the daily limit and quota was incremented.
    Returns False if user has reached the limit.
    Falls back to allow on DB error so the system does not block users due to infra issues.
    """
    today = datetime.now().strftime("%Y-%m-%d")
    settings = get_settings()
    daily_limit = settings.RATE_LIMIT_REQUESTS

    try:
        supabase = _get_supabase_client()
        response = supabase.rpc(
            "increment_quota_if_under_limit",
            {
                "p_user_id": user_id,
                "p_date": today,
                "p_daily_limit": daily_limit,
            },
        ).execute()

        # RPC returns boolean: True = allowed (and incremented), False = limit reached
        return bool(response.data)
    except Exception as e:
        logger.error(f"Error checking quota for user {user_id}: {e}")
        # If DB call fails, allow the request to avoid blocking legitimate users
        return True



async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user

    await update.message.reply_text(
        messages.WELCOME.format(first_name=user.first_name),
        parse_mode=ParseMode.HTML,
    )


def _format_source_line(source: dict) -> str:
    """Build one source line with HTML-escaped values to avoid Telegram parse errors."""
    section = source.get("section", "") or ""
    title = source.get("title", "") or ""

    if section and title and section != title:
        source_name = f"{section} — {title}"
    else:
        source_name = title or section or "Buku Panduan"

    panduan_type = detect_panduan_type(source)

    safe_name = html.escape(source_name)
    safe_panduan = html.escape(panduan_type)
    return f"  • {safe_name} (Buku Panduan {safe_panduan})\n"


async def handle_text_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return

    text = (update.message.text or "").strip()
    if not text:
        return

    chat_id = update.effective_chat.id
    user_id = str(update.effective_user.id)
    settings = get_settings()

    # Cek limit harian sebelum memproses pertanyaan.
    # Supabase client adalah sync, jalankan di thread pool agar event loop tidak terblokir.
    has_quota = await asyncio.to_thread(check_and_update_quota, user_id)
    if not has_quota:
        await update.message.reply_text(
            messages.DAILY_LIMIT_REACHED.format(limit=settings.RATE_LIMIT_REQUESTS),
            parse_mode=ParseMode.HTML,
        )
        return

    loading_message = None
    try:
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

        # Kirim pesan loading sementara
        loading_message = await update.message.reply_text(
            messages.LOADING,
            parse_mode=ParseMode.HTML,
        )

        username = update.effective_user.username or update.effective_user.full_name or "Unknown"
        response = await asyncio.to_thread(
            chat,
            query=text,
            session_id=user_id,
            username=username,
            channel="telegram",
            mahasiswa_id=None
        )

        reply_text = (response.get("answer", "")).strip()
        if not reply_text:
            reply_text = messages.EMPTY_ANSWER_FALLBACK

        # Escape jawaban agar karakter <, >, & tidak memecah parsing HTML Telegram
        safe_reply = html.escape(reply_text)

        sources = response.get("sources", [])
        if sources:
            source_text = "\n\n📚 Sumber:\n"
            for s in sources:
                source_text += _format_source_line(s)
            safe_reply += source_text

        # Update pesan loading dengan jawaban akhir
        await loading_message.edit_text(
            f"🤖 {safe_reply}",
            parse_mode=ParseMode.HTML,
        )

        num_docs = response.get("num_docs", 0)
        if num_docs > 0:
            logger.info(f"Chat response sent to user {user_id}, used {num_docs} documents")



    except Exception:
        logger.exception(f"Unexpected error in text chat handler for user {user_id}")
        error_text = messages.GENERIC_ERROR

        try:
            if loading_message is not None:
                await loading_message.edit_text(error_text, parse_mode=ParseMode.HTML)
            else:
                await update.message.reply_text(error_text, parse_mode=ParseMode.HTML)
        except Exception:
            pass


def build_text_chat_handler() -> MessageHandler:
    return MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_chat)
