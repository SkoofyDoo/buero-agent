"""Telegram bot: poll SQLite queue and send emails with action buttons."""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from telegram import Update
from telegram.error import Conflict
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from bot.config import EmailData
from bot.handlers import build_keyboard, button_handler, start
from bot.messages import format_email
from mail_queue.db import get_new_items, init_db, mark_as_processed

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(ROOT / "logs" / "bot.log", encoding="utf-8"),
    ],
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

POLL_INTERVAL_SEC = 10


def _load_settings() -> tuple[str, str | None]:
    token = os.getenv("TELEGRAM_TOKEN") or os.getenv("BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID") or os.getenv("CHAT_ID")
    if not token:
        raise SystemExit("TELEGRAM_TOKEN or BOT_TOKEN missing in .env")
    return token.strip().strip('"'), (chat_id.strip().strip('"') if chat_id else None)


async def process_queue(app: Application) -> None:
    """Send all new queue items to Telegram and mark them processed."""
    chat_id = app.bot_data.get("chat_id")
    if not chat_id:
        logger.warning("TELEGRAM_CHAT_ID missing — skip queue send. Use /start to get it.")
        return

    items = get_new_items()
    if not items:
        return

    for item in items:
        email = EmailData.from_dict(item.raw)
        text = format_email(email) or "(Keine Daten)"
        # Extra buttons in build_keyboard:
        # - Anhänge when email.attachments is not empty
        # - Termine when "create_appointments" is in email.actions
        keyboard = build_keyboard(email, item.id)

        await app.bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=keyboard,
        )
        mark_as_processed(item.id)
        logger.info("Sent queue item %s (email_id=%s)", item.id, item.email_id)


async def queue_poller(app: Application) -> None:
    """Periodically check the SQLite queue."""
    while True:
        try:
            await process_queue(app)
        except Exception:
            logger.exception("Queue poll failed")
        await asyncio.sleep(POLL_INTERVAL_SEC)


async def on_startup(app: Application) -> None:
    init_db()
    (ROOT / "logs").mkdir(parents=True, exist_ok=True)

    async def _start_poller() -> None:
        while not app.running:
            await asyncio.sleep(0.1)
        await queue_poller(app)

    asyncio.get_running_loop().create_task(_start_poller(), name="queue_poller")
    logger.info("Bot started. Polling queue every %ss.", POLL_INTERVAL_SEC)


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    err = context.error
    if isinstance(err, Conflict):
        logger.error(
            "Telegram Conflict: another bot instance is polling this token. "
            "Stop the other process and restart."
        )
        return
    logger.exception("Unhandled bot error: %s", err)


def main() -> None:
    token, chat_id = _load_settings()
    (ROOT / "logs").mkdir(parents=True, exist_ok=True)
    init_db()

    app = (
        Application.builder()
        .token(token)
        .post_init(on_startup)
        .build()
    )
    app.bot_data["chat_id"] = chat_id

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_error_handler(on_error)

    if not chat_id:
        logger.warning(
            "Set TELEGRAM_CHAT_ID in .env. Start the bot and send /start to see your chat id."
        )

    app.run_polling(
        allowed_updates=["message", "callback_query"],
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()
