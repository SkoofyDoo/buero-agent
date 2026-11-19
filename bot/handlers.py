"""Telegram callback handlers for email action buttons."""

from __future__ import annotations

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from bot.config import Appointment, EmailData
from bot.messages import format_email
from mail_queue.db import get_item

logger = logging.getLogger(__name__)

STATUS_DE = {
    "free": "frei",
    "frei": "frei",
    "conflict": "Konflikt",
    "confllict": "Konflikt",
    "busy": "belegt",
}


def build_keyboard(email: EmailData, queue_id: int) -> InlineKeyboardMarkup:
    """Build inline buttons for one queued email."""
    rows = [
        [
            InlineKeyboardButton("✅ Senden", callback_data=f"send:{queue_id}"),
            InlineKeyboardButton("✏️ Bearbeiten", callback_data=f"bearbeiten:{queue_id}"),
            InlineKeyboardButton("❌ Ignorieren", callback_data=f"ignore:{queue_id}"),
        ]
    ]
    extra: list[InlineKeyboardButton] = []
    if email.attachments:
        extra.append(
            InlineKeyboardButton("📎 Anhänge", callback_data=f"attachments:{queue_id}")
        )
    if "create_appointments" in email.actions:
        extra.append(
            InlineKeyboardButton("📅 Termine", callback_data=f"termine:{queue_id}")
        )
    if extra:
        rows.append(extra)
    return InlineKeyboardMarkup(rows)


def build_termine_keyboard(queue_id: int) -> InlineKeyboardMarkup:
    """Buttons on the Termine list screen."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✅ Alle anlegen", callback_data=f"alle:{queue_id}"
                ),
                InlineKeyboardButton("❌ Zurück", callback_data=f"back:{queue_id}"),
            ]
        ]
    )


def build_back_keyboard(queue_id: int) -> InlineKeyboardMarkup:
    """Single Zurück button for detail screens."""
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("❌ Zurück", callback_data=f"back:{queue_id}")]]
    )


def format_attachments_list(attachments: list[str]) -> str:
    """Bullet list of attachment file names."""
    names = [name.strip() for name in attachments if name and str(name).strip()]
    if not names:
        return "Keine Anhänge."
    return "\n".join(f"• {name}" for name in names)


def _format_date(date_str: str) -> str:
    """Convert YYYY-MM-DD to DD.MM.YYYY when possible."""
    parts = date_str.split("-")
    if len(parts) == 3 and all(parts):
        return f"{parts[2]}.{parts[1]}.{parts[0]}"
    return date_str


def _status_label(status: str) -> str:
    key = (status or "").strip().lower()
    if not key:
        return ""
    return STATUS_DE.get(key, status)


def format_termine_list(appointments: list[Appointment]) -> str:
    """
    Numbered appointment list, e.g.:
    1. 19.11.2026 14:00 — Gespräch (frei)
    """
    if not appointments:
        return "Keine Termine."

    lines: list[str] = []
    for index, appt in enumerate(appointments, start=1):
        date = _format_date(appt.date) if appt.date else ""
        time = appt.time or ""
        when = " ".join(part for part in (date, time) if part).strip()
        title = appt.title or "Termin"
        status = _status_label(appt.status)

        line = f"{index}. "
        if when:
            line += f"{when} — {title}"
        else:
            line += title
        if status:
            line += f" ({status})"
        lines.append(line)

    return "\n".join(lines)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show chat id so the user can put it into .env."""
    chat = update.effective_chat
    if chat is None or update.message is None:
        return
    await update.message.reply_text(
        "Büro-Agent ist bereit.\n"
        f"CHAT_ID: `{chat.id}`\n"
        "Trage TELEGRAM_CHAT_ID in die .env ein.",
        parse_mode="Markdown",
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle email action and Termine buttons."""
    query = update.callback_query
    if query is None or not query.data:
        return

    await query.answer()

    action, _, raw_id = query.data.partition(":")
    if not raw_id.isdigit():
        await query.edit_message_text("Ungültige Aktion.")
        return

    queue_id = int(raw_id)

    if action == "send":
        await query.edit_message_text("Отправлено")
        return

    if action == "bearbeiten":
        await query.edit_message_text("Режим редактирования")
        return

    if action == "ignore":
        await query.edit_message_text("Проигнорировано")
        return

    if action == "attachments":
        item = get_item(queue_id)
        if item is None:
            await query.edit_message_text("Keine Anhänge gefunden.")
            return
        text = format_attachments_list(item.email.attachments)
        await query.edit_message_text(
            text,
            reply_markup=build_back_keyboard(queue_id),
        )
        return

    if action == "termine":
        item = get_item(queue_id)
        if item is None:
            await query.edit_message_text("Keine Termine gefunden.")
            return
        text = format_termine_list(item.email.appointments)
        await query.edit_message_text(
            text,
            reply_markup=build_termine_keyboard(queue_id),
        )
        return

    if action == "alle":
        # Stub: no real calendar events yet.
        await query.edit_message_text("Termine werden angelegt (demnächst).")
        return

    if action == "back":
        item = get_item(queue_id)
        if item is None:
            await query.edit_message_text("Nachricht nicht gefunden.")
            return
        email = item.email
        text = format_email(email) or "(Keine Daten)"
        await query.edit_message_text(
            text,
            reply_markup=build_keyboard(email, queue_id),
        )
        return

    logger.warning("Unknown callback action: %s", action)
    await query.edit_message_text("Unbekannte Aktion.")
