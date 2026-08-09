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
        # Same real fix as vinu_infra.sqlite.SQLiteBackend: track every
        # connection opened by any thread so close() can close all of them,
        # and a generation counter so a thread whose connection was closed
        # by another thread's close() call reopens instead of reusing (and
        # getting sqlite3.ProgrammingError from) a stale closed connection.
        self._all_conns: list[sqlite3.Connection] = []
        self._all_conns_lock = threading.Lock()
        self._generation = 0

    def _get_conn(self) -> sqlite3.Connection:
        conn: sqlite3.Connection | None = getattr(self._local, "conn", None)
        if conn is None or getattr(self._local, "gen", -1) != self._generation:
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
            self._local.gen = self._generation
            with self._all_conns_lock:
                self._all_conns.append(conn)
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
        with self._all_conns_lock:
            conns, self._all_conns = self._all_conns, []
            self._generation += 1
        for conn in conns:
            try:
                conn.close()
            except sqlite3.Error:
                pass
        self._local.conn = None
