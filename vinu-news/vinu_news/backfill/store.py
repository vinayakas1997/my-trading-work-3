from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any


@dataclass
class BackfillStatusView:
    ticker: str
    enabled: bool
    status: str
    backfilled_up_to_ts: int | None
    oldest_ts: int | None
    article_count: int
    error_message: str | None
    updated_at: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticker": self.ticker,
            "enabled": self.enabled,
            "status": self.status,
            "backfilled_up_to_ts": self.backfilled_up_to_ts,
            "oldest_ts": self.oldest_ts,
            "article_count": self.article_count,
            "error_message": self.error_message,
            "updated_at": self.updated_at,
        }


class BackfillStore:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def init_schema(self, schema_sql: str) -> None:
        self._conn.executescript(schema_sql)

    def get_all(self) -> list[BackfillStatusView]:
        rows = self._conn.execute(
            "SELECT * FROM backfill_status ORDER BY ticker"
        ).fetchall()
        return [_row_to_view(r) for r in rows]

    def get(self, ticker: str) -> BackfillStatusView | None:
        row = self._conn.execute(
            "SELECT * FROM backfill_status WHERE ticker = ?",
            (ticker.upper(),),
        ).fetchone()
        return _row_to_view(row) if row else None

    def upsert(self, ticker: str, **fields: Any) -> None:
        ticker = ticker.upper()
        cols = ", ".join(fields.keys())
        placeholders = ", ".join("?" for _ in fields)
        updates = ", ".join(f"{k} = excluded.{k}" for k in fields)
        self._conn.execute(
            f"""
            INSERT INTO backfill_status (ticker, {cols})
            VALUES (?, {placeholders})
            ON CONFLICT(ticker) DO UPDATE SET {updates}
            """,
            [ticker] + list(fields.values()),
        )
        self._conn.commit()

    def toggle(self, ticker: str, enabled: bool) -> None:
        self._conn.execute(
            "UPDATE backfill_status SET enabled = ?, updated_at = ? WHERE ticker = ?",
            (1 if enabled else 0, _now(), ticker.upper()),
        )
        self._conn.commit()

    def list_enabled(self) -> list[BackfillStatusView]:
        rows = self._conn.execute(
            "SELECT * FROM backfill_status WHERE enabled = 1 AND status != 'completed' ORDER BY ticker"
        ).fetchall()
        return [_row_to_view(r) for r in rows]

    def ensure_ticker(self, ticker: str) -> None:
        existing = self.get(ticker)
        if existing is None:
            now = _now()
            self._conn.execute(
                "INSERT INTO backfill_status (ticker, enabled, status, updated_at) VALUES (?, 1, 'pending', ?)",
                (ticker.upper(), now),
            )
            self._conn.commit()


def _row_to_view(row: sqlite3.Row) -> BackfillStatusView:
    return BackfillStatusView(
        ticker=row["ticker"],
        enabled=bool(row["enabled"]),
        status=row["status"],
        backfilled_up_to_ts=row["backfilled_up_to_ts"],
        oldest_ts=row["oldest_ts"],
        article_count=row["article_count"],
        error_message=row["error_message"],
        updated_at=row["updated_at"],
    )


def _now() -> int:
    import time
    return int(time.time())
