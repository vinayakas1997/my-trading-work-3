"""SQLite cache for LLM article analysis (TASK-N01)."""

from __future__ import annotations

import json
import sqlite3
import time
from typing import Any


def get_cached_analysis(
    conn: sqlite3.Connection,
    url: str,
    *,
    ttl_sec: int,
) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT analysis_json, created_at FROM news_analysis WHERE url = ?",
        (url,),
    ).fetchone()
    if not row:
        return None
    created_at = int(row["created_at"])
    if ttl_sec > 0 and int(time.time()) - created_at > ttl_sec:
        return None
    return json.loads(row["analysis_json"])


def save_analysis(conn: sqlite3.Connection, url: str, analysis: dict[str, Any]) -> None:
    now = int(time.time())
    conn.execute(
        """
        INSERT INTO news_analysis (url, analysis_json, created_at)
        VALUES (?, ?, ?)
        ON CONFLICT(url) DO UPDATE SET
            analysis_json = excluded.analysis_json,
            created_at = excluded.created_at
        """,
        (url, json.dumps(analysis), now),
    )
    conn.commit()
