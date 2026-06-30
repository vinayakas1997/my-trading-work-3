"""Watchlist ticker registry."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any


class WatchlistStore:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def init_schema(self, schema_sql: str) -> None:
        self._conn.executescript(schema_sql)

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
                INSERT OR IGNORE INTO watchlist_tickers (ticker, added_at)
                VALUES (?, ?)
                """,
                (symbol, now),
            )
            if cursor.rowcount > 0:
                added.append(symbol)
        self._conn.commit()
        return added

    def remove_ticker(self, ticker: str) -> bool:
        symbol = ticker.strip().upper()
        cursor = self._conn.execute(
            "DELETE FROM watchlist_tickers WHERE ticker = ?",
            (symbol,),
        )
        self._conn.commit()
        return cursor.rowcount > 0

    def to_dict(self) -> dict[str, Any]:
        return {"tickers": self.list_tickers()}
