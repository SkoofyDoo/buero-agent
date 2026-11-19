"""Cross-platform Hermes poller: Email → Hermes → SQLite queue.

Run:
  python -m pipeline.poller

Env:
  BUERO_POLL_INTERVAL  seconds between runs (default 300)
  BUERO_HERMES_QUERY   override Hermes prompt
  HERMES_BIN           hermes executable (default: hermes)

On VPS wrap with systemd (see deploy/ later). Alternative: Hermes cron
with `--script` pointing at `run_hermes.py --once` if you prefer Hermes
to own the schedule.
"""

from __future__ import annotations

import logging
import os
import signal
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

from pipeline.hermes_ingest import ROOT, run_once

LOCK_PATH = ROOT / "data" / "poller.lock"
LOG_PATH = ROOT / "logs" / "poller.log"

log = logging.getLogger("pipeline.poller")

_stop = False


class PollerLock:
    """Exclusive file lock (Windows msvcrt / Unix fcntl), no extra deps."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._fh = None

    def acquire(self) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(self.path, "a+", encoding="utf-8")
        try:
            if os.name == "nt":
                import msvcrt

                self._fh.seek(0)
                try:
                    msvcrt.locking(self._fh.fileno(), msvcrt.LK_NBLCK, 1)
                except OSError:
                    return False
            else:
                import fcntl

                try:
                    fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                except OSError:
                    return False
        except Exception:
            self.release()
            raise

        self._fh.seek(0)
        self._fh.truncate()
        self._fh.write(f"pid={os.getpid()}\n")
        self._fh.flush()
        return True

    def release(self) -> None:
        if self._fh is None:
            return
        try:
            if os.name == "nt":
                import msvcrt

                self._fh.seek(0)
                try:
                    msvcrt.locking(self._fh.fileno(), msvcrt.LK_UNLCK, 1)
                except OSError:
                    pass
            else:
                import fcntl

                fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
        finally:
            try:
                self._fh.close()
            except OSError:
                pass
            self._fh = None


def _setup_logging() -> None:
    (ROOT / "logs").mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    if root.handlers:
        return
    root.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    for handler in (
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
    ):
        handler.setFormatter(fmt)
        root.addHandler(handler)


def _request_stop(signum: int, _frame: object) -> None:
    global _stop
    _stop = True
    log.info("Stop requested (signal %s)", signum)


def _poll_interval() -> int:
    raw = os.getenv("BUERO_POLL_INTERVAL", "300").strip()
    try:
        value = int(raw)
    except ValueError:
        log.warning("Invalid BUERO_POLL_INTERVAL=%r — using 300", raw)
        return 300
    return max(30, value)


def _interruptible_sleep(seconds: int) -> None:
    """Sleep in short slices so SIGINT/SIGTERM can stop the poller quickly."""
    end = time.time() + seconds
    while not _stop and time.time() < end:
        time.sleep(min(1.0, end - time.time()))


def main() -> int:
    load_dotenv(ROOT / ".env")
    _setup_logging()

    interval = _poll_interval()
    lock = PollerLock(LOCK_PATH)
    if not lock.acquire():
        log.error("Another poller holds %s — exiting", LOCK_PATH)
        return 1

    signal.signal(signal.SIGINT, _request_stop)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _request_stop)

    log.info("Poller started. interval=%ss lock=%s", interval, LOCK_PATH)
    exit_code = 0
    try:
        while not _stop:
            try:
                result = run_once()
                log.info(
                    "Tick done reason=%s queue_id=%s email_id=%s",
                    result.reason,
                    result.queue_id,
                    result.email_id,
                )
            except Exception:
                log.exception("Ingest tick failed")
                exit_code = 1

            if _stop:
                break
            _interruptible_sleep(interval)
    finally:
        lock.release()
        log.info("Poller stopped")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
