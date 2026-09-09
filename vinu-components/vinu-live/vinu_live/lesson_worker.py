"""Lesson worker (20 step1): memory starts day 1, lesson after 30 trades.

Minimal v1: counts closed positions in trade_plan_book.db. When closed >=
VINU_LESSON_MIN_TRADES (default 30), writes a LESSON JSON to data/live/lessons/.
Calibration wire already exists via scheduler_workers angle trust (low_trust
de-prioritized, never gated). Interval 3600s via VINU_LESSON_INTERVAL_SEC.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

LOG = logging.getLogger(__name__)


def lesson_dir(data_root: Path | str = "") -> Path:
    root = Path(data_root) if data_root else Path(os.environ.get("VINU_LIVE_DATA_ROOT", "data/live"))
    d = root / "lessons"
    d.mkdir(parents=True, exist_ok=True)
    return d


def should_write_lesson(closed_count: int, min_trades: int | None = None) -> bool:
    mt = min_trades if min_trades is not None else int(os.environ.get("VINU_LESSON_MIN_TRADES", "30"))
    return closed_count >= mt


def write_lesson(summary: dict, data_root: Path | str = "") -> Path:
    d = lesson_dir(data_root)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    p = d / f"LESSON_{ts}.json"
    p.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    LOG.info("Lesson written %s", p)
    return p


def cycle(data_root: Path | str = "", db_path: Path | str = "") -> dict:
    """One lesson cycle: count closed, write LESSON when >= MIN_TRADES."""
    import sqlite3

    root = Path(data_root) if data_root else Path(os.environ.get("VINU_LIVE_DATA_ROOT", "data/live"))
    db = Path(db_path) if db_path else root / "trade_plan_book.db"
    if not db.exists():
        return {"status": "skipped_no_db", "closed": 0}
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        cur = con.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='closed_positions'")
        if cur.fetchone():
            cur.execute("SELECT COUNT(*) FROM closed_positions")
        else:
            cur.execute("SELECT COUNT(*) FROM positions WHERE status='closed'")
        closed = cur.fetchone()[0]
    except Exception as e:
        return {"status": "failed", "error": str(e)}
    finally:
        con.close()
    if not should_write_lesson(closed):
        return {"status": "skipped_not_enough", "closed": closed}
    p = write_lesson({"closed": closed, "at": datetime.now(timezone.utc).isoformat()}, root)
    return {"status": "ok", "closed": closed, "lesson": str(p)}
