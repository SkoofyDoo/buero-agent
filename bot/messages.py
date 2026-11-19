"""Format Hermes email JSON for Telegram messages."""

from __future__ import annotations

from typing import Any


def _text(value: Any) -> str:
    """Return a stripped string, or empty if missing."""
    if value is None:
        return ""
    return str(value).strip()


def _has_content(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, (list, dict)):
        return bool(value)
    return bool(_text(value))


def _format_sender(data: dict[str, Any]) -> str:
    name = _text(data.get("from_name"))
    email = _text(data.get("from") or data.get("sender"))
    if name and email:
        return f"{name} <{email}>"
    return name or email


def _format_list_items(items: list[Any]) -> list[str]:
    lines: list[str] = []
    for item in items:
        if isinstance(item, dict):
            label = (
                _text(item.get("filename"))
                or _text(item.get("name"))
                or _text(item.get("term"))
                or _text(item.get("title"))
            )
            extra = _text(item.get("description") or item.get("value"))
            if label and extra:
                lines.append(f"• {label}: {extra}")
            elif label:
                lines.append(f"• {label}")
            elif extra:
                lines.append(f"• {extra}")
        else:
            text = _text(item)
            if text:
                lines.append(f"• {text}")
    return lines


def format_email(data: dict[str, Any]) -> str:
    """Turn Hermes JSON into a readable Telegram message (German labels)."""
    blocks: list[str] = []

    sender = _format_sender(data)
    if sender:
        blocks.append(f"Von: {sender}")

    subject = _text(data.get("subject") or data.get("betreff"))
    if subject:
        blocks.append(f"Betreff: {subject}")

    summary = _text(data.get("summary") or data.get("zusammenfassung"))
    if summary:
        blocks.append(f"Zusammenfassung:\n{summary}")

    # Anhänge
    attachments = data.get("attachments") or data.get("anhaenge") or []
    if _has_content(attachments):
        if isinstance(attachments, list):
            lines = _format_list_items(attachments)
        else:
            lines = [f"• {_text(attachments)}"]
        if lines:
            blocks.append("Anhänge:\n" + "\n".join(lines))

    # Termine
    appointments = data.get("appointments") or []
    if appointments:
        lines = []
        for appt in appointments:
            line = f"• {appt.get('date')} {appt.get('time')} — {appt.get('title')}"
            lines.append(line)
        blocks.append("Termine:\n" + "\n".join(lines))

    # Typ
    email_type = _text(data.get("type"))
    if email_type:
        blocks.append(f"Typ: {email_type}")

    draft = _text(data.get("draft") or data.get("entwurf") or data.get("reply_draft"))
    if draft:
        blocks.append(f"Entwurf:\n{draft}")

    return "\n\n".join(blocks).strip()
