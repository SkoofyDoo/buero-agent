"""One-shot Hermes email ingest into the SQLite queue.

Shared by:
- `python run_hermes.py` (manual)
- `python -m pipeline.poller` (scheduled loop)
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from mail_queue.db import add_to_queue, email_id_exists, init_db

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_JSON = ROOT / "output.json"

DEFAULT_QUERY = "/buro-email-agent Prüfe neue E-Mails"
NO_EMAIL_ERRORS = frozenset({"no_emails", "no_email", "none"})


@dataclass(frozen=True)
class IngestResult:
    """Outcome of a single Hermes ingest attempt."""

    code: int
    reason: str
    queue_id: int | None = None
    email_id: str | None = None
    subject: str | None = None

    @property
    def ok(self) -> bool:
        return self.code == 0


def extract_json(text: str) -> dict | None:
    """Parse the last complete JSON object from Hermes stdout."""
    if not text:
        return None

    decoder = json.JSONDecoder()
    last_obj: dict | None = None
    i = 0
    while i < len(text):
        start = text.find("{", i)
        if start < 0:
            break
        try:
            obj, end = decoder.raw_decode(text, start)
        except json.JSONDecodeError:
            i = start + 1
            continue
        if isinstance(obj, dict):
            last_obj = obj
        i = end
    return last_obj


def load_fresh_output_file(started_at: float) -> dict | None:
    """Read output.json only if it was rewritten during this run."""
    if not OUTPUT_JSON.exists():
        return None

    try:
        mtime = OUTPUT_JSON.stat().st_mtime
    except OSError as exc:
        log.warning("Could not stat %s: %s", OUTPUT_JSON, exc)
        return None

    if mtime + 1 < started_at:
        log.info("Ignoring stale %s", OUTPUT_JSON.name)
        return None

    try:
        data = json.loads(OUTPUT_JSON.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("Could not read %s: %s", OUTPUT_JSON, exc)
        return None

    return data if isinstance(data, dict) else None


def save_output_file(data: dict) -> None:
    """Cache the latest Hermes JSON for debugging."""
    try:
        OUTPUT_JSON.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        log.warning("Could not write %s: %s", OUTPUT_JSON, exc)


def _hermes_cmd(query: str) -> list[str]:
    hermes_bin = os.getenv("HERMES_BIN", "hermes").strip() or "hermes"
    return [hermes_bin, "chat", "-q", query, "--oneshot", "-Q"]


def run_hermes(query: str | None = None) -> subprocess.CompletedProcess[str]:
    q = (query or os.getenv("BUERO_HERMES_QUERY") or DEFAULT_QUERY).strip()
    cmd = _hermes_cmd(q)
    log.info("Running: %s", " ".join(cmd))
    return subprocess.run(
        cmd,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def run_once(query: str | None = None) -> IngestResult:
    """
    Run Hermes once and enqueue a new email if found.

    Returns IngestResult with reason:
    - queued
    - no_emails
    - duplicate
    - no_json
    - missing_email_id
    - hermes_error (non-zero exit, still may have JSON)
    """
    init_db()
    started_at = time.time()
    result = run_hermes(query=query)

    if result.returncode != 0:
        log.error("Hermes exited with code %s", result.returncode)
        if result.stderr:
            log.error("stderr:\n%s", result.stderr.strip())

    data = extract_json(result.stdout) or load_fresh_output_file(started_at)
    if not data:
        if result.stdout:
            log.info("stdout tail:\n%s", result.stdout[-1000:])
        if result.stderr:
            log.info("stderr:\n%s", result.stderr.strip())
        return IngestResult(code=1, reason="no_json")

    error = str(data.get("error") or "").strip().lower()
    if error in NO_EMAIL_ERRORS:
        save_output_file(data)
        log.info("No new emails (%s)", error)
        return IngestResult(code=0, reason="no_emails")

    email_id = str(data.get("email_id") or "").strip()
    subject = str(data.get("subject") or "") or None
    if not email_id:
        log.error("JSON has no email_id")
        return IngestResult(code=1, reason="missing_email_id")

    if email_id_exists(email_id):
        save_output_file(data)
        log.info("Skip duplicate email_id=%s subject=%s", email_id, subject or "—")
        return IngestResult(
            code=0,
            reason="duplicate",
            email_id=email_id,
            subject=subject,
        )

    queue_id = add_to_queue(data, email_id=email_id)
    save_output_file(data)
    log.info(
        "Queued id=%s email_id=%s subject=%s draft=%s",
        queue_id,
        email_id,
        subject or "—",
        "yes" if str(data.get("draft") or "").strip() else "empty",
    )
    return IngestResult(
        code=0,
        reason="queued",
        queue_id=queue_id,
        email_id=email_id,
        subject=subject,
    )
