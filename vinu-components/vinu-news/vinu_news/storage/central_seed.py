"""Fresh start of the news store: carry the configuration forward, leave the news behind.

The legacy shared database `vinu_news.db` is never opened for writing again (it stays as the archive). A new central
database receives only what is configuration: settings, the watchlist, the backfill list (every ticker reset to `pending`, so
the per-ticker backfill fetches it again from the start date) and the source switches and health.
"""
from __future__ import annotations

import logging
import sqlite3
import time
from pathlib import Path
from typing import Any

LOG = logging.getLogger(__name__)


def seed_central_from_legacy(central: Any, legacy_path: str | Path) -> dict[str, int]:
    legacy_path = Path(legacy_path)
    if not legacy_path.exists():
        return {}
    src = sqlite3.connect(f"file:{legacy_path.as_posix()}?mode=ro", uri=True, timeout=10)
    src.row_factory = sqlite3.Row
    counts: dict[str, int] = {}
    try:
        conn = central.repo.conn
        with conn:
            for key, value in _rows(src, "SELECT key, value FROM vinu_settings"):
                conn.execute("INSERT OR REPLACE INTO vinu_settings (key, value) VALUES (?, ?)", (key, value))
                counts["settings"] = counts.get("settings", 0) + 1
            for ticker, added_at, pending in _rows(src, "SELECT ticker, added_at, pending_fetch FROM watchlist_tickers"):
                conn.execute("INSERT OR IGNORE INTO watchlist_tickers (ticker, added_at, pending_fetch) VALUES (?, ?, ?)",
                             (ticker, added_at, pending))
                counts["watchlist"] = counts.get("watchlist", 0) + 1
            now = int(time.time())
            for ticker, enabled in _rows(src, "SELECT ticker, enabled FROM backfill_status"):
                conn.execute(
                    "INSERT OR IGNORE INTO backfill_status (ticker, enabled, status, backfilled_up_to_ts, oldest_ts, "
                    "article_count, error_message, updated_at) VALUES (?, ?, 'pending', NULL, NULL, 0, NULL, ?)",
                    (ticker, enabled, now))
                counts["backfill"] = counts.get("backfill", 0) + 1
            cols = [r[1] for r in src.execute("PRAGMA table_info(feed_health)").fetchall()]
            for row in src.execute("SELECT * FROM feed_health").fetchall():
                names = [c for c in cols if c in {r[1] for r in conn.execute("PRAGMA table_info(feed_health)").fetchall()}]
                conn.execute(
                    f"INSERT OR IGNORE INTO feed_health ({', '.join(names)}) VALUES ({', '.join('?' for _ in names)})",
                    tuple(row[c] for c in names))
                counts["source_health"] = counts.get("source_health", 0) + 1
    finally:
        src.close()
    LOG.info("fresh start: central news database seeded from %s: %s", legacy_path, counts)
    return counts


def _rows(src: sqlite3.Connection, sql: str):
    try:
        return [tuple(r) for r in src.execute(sql).fetchall()]
    except sqlite3.OperationalError:
        return []
