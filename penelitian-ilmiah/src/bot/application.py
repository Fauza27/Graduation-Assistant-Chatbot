from telegram import BotCommand, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)
from loguru import logger

from src.bot import messages
from src.bot.handlers import chat_handler
from config.settings import get_settings


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Unhandled exception", exc_info=context.error)

    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                messages.GENERIC_ERROR,
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            pass


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        messages.HELP,
        parse_mode=ParseMode.HTML,
    )


async def post_init(application: Application) -> None:
    await application.bot.set_my_commands(
        [
            BotCommand("start", "Mulai bot"),
            BotCommand("help", "Lihat bantuan"),
        ]
    )


def create_bot() -> Application:
    settings = get_settings()

    app = (
        ApplicationBuilder()
        .token(settings.TELEGRAM_BOT_TOKEN)
        .concurrent_updates(False)
        .build()
    )

    app.add_error_handler(error_handler)

    app.add_handler(CommandHandler("start", chat_handler.cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))

    app.add_handler(chat_handler.build_text_chat_handler())

    return app
