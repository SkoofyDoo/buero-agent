"""Format EmailData for Telegram messages."""

from __future__ import annotations

from bot.config import Appointment, EmailData


def _format_sender(email: EmailData) -> str:
    if email.from_name and email.from_email:
        return f"{email.from_name} <{email.from_email}>"
    return email.from_name or email.from_email


def _format_appointment(appt: Appointment) -> str:
    when = " ".join(part for part in (appt.date, appt.time) if part).strip()
    if when and appt.title:
        return f"• {when} — {appt.title}"
    if when:
        return f"• {when}"
    if appt.title:
        return f"• {appt.title}"
    return ""


def format_email(email: EmailData) -> str:
    """Turn EmailData into a readable Telegram message (German labels)."""
    header: list[str] = []
    blocks: list[str] = []

    sender = _format_sender(email)
    if sender:
        header.append(f"Von: {sender}")

    if email.subject:
        header.append(f"Betreff: {email.subject}")

    if email.client.name:
        header.append(f"Kunde: {email.client.name}")

    if header:
        blocks.append("\n".join(header))

    if email.summary:
        blocks.append(f"Zusammenfassung:\n{email.summary}")

    attachment_lines = [f"• {name}" for name in email.attachments if name]
    if attachment_lines:
        blocks.append("Anhänge:\n" + "\n".join(attachment_lines))

    appointment_lines = [
        line for line in (_format_appointment(a) for a in email.appointments) if line
    ]
    if appointment_lines:
        blocks.append("Termine:\n" + "\n".join(appointment_lines))

    if email.draft:
        blocks.append(f"Entwurf:\n{email.draft}")

    return "\n\n".join(blocks).strip()
