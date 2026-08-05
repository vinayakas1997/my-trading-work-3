from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any


class LlmCache:
    def __init__(self, cache_path: str | Path, ttl_sec: int = 86400) -> None:
        self._path = Path(cache_path)
        self._ttl = ttl_sec
        self._local = threading.local()

    def _get_conn(self) -> sqlite3.Connection:
        conn: sqlite3.Connection | None = getattr(self._local, "conn", None)
        if conn is None:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(self._path))
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(
                "CREATE TABLE IF NOT EXISTS llm_cache ("
                "  cache_key TEXT PRIMARY KEY,"
                "  response_json TEXT NOT NULL,"
                "  created_at INTEGER NOT NULL"
                ")"
            )
            self._local.conn = conn
        return conn

    def get(self, cache_key: str) -> dict[str, Any] | None:
        if self._ttl <= 0:
            return None
        conn = self._get_conn()
        row = conn.execute(
            "SELECT response_json, created_at FROM llm_cache WHERE cache_key=?",
            (cache_key,),
        ).fetchone()
        if row is None:
            return None
        if time.time() - row[1] > self._ttl:
            conn.execute("DELETE FROM llm_cache WHERE cache_key=?", (cache_key,))
            conn.commit()
            return None
        try:
            return json.loads(row[0])
        except json.JSONDecodeError:
            return None

    def set(self, cache_key: str, data: dict[str, Any]) -> None:
        conn = self._get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO llm_cache (cache_key, response_json, created_at) VALUES (?, ?, ?)",
            (cache_key, json.dumps(data), int(time.time())),
        )
        conn.commit()

    def close(self) -> None:
        conn: sqlite3.Connection | None = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None
