"""Watchlist ticker registry."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any


class WatchlistStore:
    """CRUD for watchlist_tickers table."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def init_schema(self, schema_sql: str) -> None:
        self._conn.executescript(schema_sql)
        self._migrate()

    def _migrate(self) -> None:
        cols = {row["name"] for row in self._conn.execute("PRAGMA table_info(watchlist_tickers)")}
        if "pending_fetch" not in cols:
            self._conn.execute(
                "ALTER TABLE watchlist_tickers ADD COLUMN pending_fetch INTEGER NOT NULL DEFAULT 0"
            )
            self._conn.commit()

    def list_tickers(self) -> list[str]:
        rows = self._conn.execute(
            "SELECT ticker FROM watchlist_tickers ORDER BY added_at ASC, ticker ASC"
        ).fetchall()
        return [row["ticker"] for row in rows]

    def add_tickers(self, tickers: list[str]) -> list[str]:
        now = int(datetime.now(timezone.utc).timestamp())
        added: list[str] = []
        for raw in tickers:
            symbol = raw.strip().upper()
            if not symbol:
                continue
            cursor = self._conn.execute(
                """
                INSERT OR IGNORE INTO watchlist_tickers (ticker, added_at, pending_fetch)
                VALUES (?, ?, 1)
                """,
                (symbol, now),
            )
            if cursor.rowcount > 0:
                added.append(symbol)
        self._conn.commit()
        return added

    def list_pending(self) -> list[str]:
        rows = self._conn.execute(
            "SELECT ticker FROM watchlist_tickers WHERE pending_fetch = 1 ORDER BY added_at ASC"
        ).fetchall()
        return [row["ticker"] for row in rows]

    def clear_pending(self, tickers: list[str]) -> None:
        if not tickers:
            return
        placeholders = ",".join("?" for _ in tickers)
        self._conn.execute(
            f"UPDATE watchlist_tickers SET pending_fetch = 0 WHERE ticker IN ({placeholders})",
            tickers,
        )
        self._conn.commit()

    def clear_all_pending(self) -> None:
        self._conn.execute("UPDATE watchlist_tickers SET pending_fetch = 0 WHERE pending_fetch = 1")
        self._conn.commit()

    def remove_ticker(self, ticker: str) -> bool:
        symbol = ticker.strip().upper()
        cursor = self._conn.execute(
            "DELETE FROM watchlist_tickers WHERE ticker = ?",
            (symbol,),
        )
        self._conn.commit()
        return cursor.rowcount > 0

    def as_set(self) -> set[str]:
        return set(self.list_tickers())

    def to_dict(self) -> dict[str, Any]:
        return {"tickers": self.list_tickers()}
