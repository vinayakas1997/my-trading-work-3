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
    # PRIDE star (20): high-evidence lessons (>=STAR_MIN closed) get STAR
    # prefix so review prioritizes them. Threshold env, default 50.
    try:
        _star_min = int(os.environ.get("VINU_LESSON_STAR_MIN", "50"))
    except ValueError:
        _star_min = 50
    d = lesson_dir(data_root)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    star = "STAR_" if (summary.get("closed", 0) or 0) >= _star_min else ""
    p = d / f"{star}LESSON_{ts}.json"
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
        # Slippage feedback input (16): realized fill costs per lesson so
        # monthly review can compare modeled vs realized. Fail-open zeros.
        fills = 0
        avg_commission = 0.0
        try:
            cur.execute("SELECT COUNT(*), AVG(commission) FROM fills")
            row = cur.fetchone()
            fills = row[0] or 0
            avg_commission = round(row[1] or 0.0, 4)
        except Exception:
            pass
        # Regime context (20): last-5 W/L streak + HALT state at lesson time,
        # so review can split lessons by market context. Fail-open empty.
        last5 = ""
        try:
            cur.execute("SELECT realized_pnl FROM closed_positions ORDER BY closed_at DESC LIMIT 5")
            last5 = "".join("W" if (r[0] or 0) >= 0 else "L" for r in cur.fetchall())
        except Exception:
            pass
    except Exception as e:
        return {"status": "failed", "error": str(e)}
    finally:
        con.close()
    halted = (Path.home() / ".vinu-live" / "HALT").exists()
    summary = {"closed": closed, "fills": fills, "avg_commission": avg_commission, "last5": last5, "halted": halted, "at": datetime.now(timezone.utc).isoformat()}
    if not should_write_lesson(closed):
        return {"status": "skipped_not_enough", **summary}
    p = write_lesson(summary, root)
    return {"status": "ok", **summary, "lesson": str(p)}
