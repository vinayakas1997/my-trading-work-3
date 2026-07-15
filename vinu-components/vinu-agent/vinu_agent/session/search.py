import json
import sqlite3
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional


class FTSSearch:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self) -> None:
        with self._lock:
            conn = sqlite3.connect(str(self._db_path))
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5("
                "session_id, role, content, message_id UNINDEXED"
                ")"
            )
            conn.commit()
            conn.close()

    def index_message(
        self, session_id: str, message_id: str, role: str, content: str
    ) -> None:
        with self._lock:
            conn = sqlite3.connect(str(self._db_path))
            conn.execute(
                "INSERT OR REPLACE INTO messages_fts (session_id, role, content, message_id) "
                "VALUES (?, ?, ?, ?)",
                (session_id, role, content, message_id),
            )
            conn.commit()
            conn.close()

    def search(
        self, query: str, limit: int = 20
    ) -> List[Dict[str, Any]]:
        with self._lock:
            conn = sqlite3.connect(str(self._db_path))
            conn.row_factory = sqlite3.Row
            try:
                rows = conn.execute(
                    "SELECT session_id, role, snippet(messages_fts, 1, '<b>', '</b>', '...', 32) AS highlighted, "
                    "rank FROM messages_fts WHERE messages_fts MATCH ? ORDER BY rank LIMIT ?",
                    (query, limit),
                ).fetchall()
                return [dict(r) for r in rows]
            except sqlite3.OperationalError:
                return []
            finally:
                conn.close()
