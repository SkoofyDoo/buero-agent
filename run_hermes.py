"""Manual one-shot: Hermes email skill → SQLite queue.

For continuous polling use:
  python -m pipeline.poller
"""

from __future__ import annotations

import logging
import sys

from dotenv import load_dotenv

from pipeline.hermes_ingest import ROOT, run_once

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


def main() -> int:
    load_dotenv(ROOT / ".env")
    result = run_once()
    return result.code


if __name__ == "__main__":
    sys.exit(main())
