#!/usr/bin/env python3
"""Main entry point: fetch Kalshi odds → generate HTML → save snapshot.

Usage:
    python scripts/refresh.py
"""

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import structlog

from src.config import settings
from src.html_gen import generate_html
from src.odds import fetch_odds, odds_to_snapshot

structlog.configure(
    processors=[
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.BoundLogger,
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)

logger = structlog.get_logger()


def save_snapshot(snapshot: list[dict], snapshot_dir: Path) -> Path:
    """Save odds snapshot as JSON file with timestamp."""
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(UTC)
    filename = now.strftime("%Y-%m-%dT%H-%M") + ".json"
    path = snapshot_dir / filename
    path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    logger.info("Snapshot saved", path=str(path))
    return path


def main():
    logger.info("Starting refresh", base_url=settings.kalshi_base_url)

    # 1. Fetch odds from Kalshi
    odds = fetch_odds()
    logger.info("Odds fetched", teams=len(odds))

    # 2. Generate static HTML
    html_path = Path(settings.html_output_path)
    generate_html(odds, html_path)

    # 3. Save snapshot
    snapshot = odds_to_snapshot(odds)
    snapshot_dir = Path(settings.snapshot_dir)
    save_snapshot(snapshot, snapshot_dir)

    logger.info("Refresh complete", html=str(html_path))


if __name__ == "__main__":
    main()
