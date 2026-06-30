"""Symbol catalog and job tracking (meta.db)."""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class SymbolCatalogEntry:
    symbol: str
    provider: str
    interval: str
    first_bar_ts: int | None
    last_bar_ts: int | None
    archive_through: str | None
    live_file: str | None
    backfill_status: str
    updated_at: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "provider": self.provider,
            "interval": self.interval,
            "first_bar_ts": self.first_bar_ts,
            "last_bar_ts": self.last_bar_ts,
            "archive_through": self.archive_through,
            "live_file": self.live_file,
            "backfill_status": self.backfill_status,
            "updated_at": self.updated_at,
        }


class CatalogStore:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._conn.row_factory = sqlite3.Row

    def init_schema(self, schema_sql: str) -> None:
        self._conn.executescript(schema_sql)

    def get_symbol(self, symbol: str) -> SymbolCatalogEntry | None:
        row = self._conn.execute(
            "SELECT * FROM symbol_catalog WHERE symbol = ?",
            (symbol.strip().upper(),),
        ).fetchone()
        return self._row_to_entry(row) if row else None

    def list_symbols(self) -> list[SymbolCatalogEntry]:
        rows = self._conn.execute(
            "SELECT * FROM symbol_catalog ORDER BY symbol ASC"
        ).fetchall()
        return [self._row_to_entry(row) for row in rows]

    def upsert_symbol(
        self,
        symbol: str,
        *,
        provider: str | None = None,
        first_bar_ts: int | None = None,
        last_bar_ts: int | None = None,
        archive_through: str | None = None,
        live_file: str | None = None,
        backfill_status: str | None = None,
    ) -> SymbolCatalogEntry:
        sym = symbol.strip().upper()
        now = int(time.time())
        existing = self.get_symbol(sym)
        if existing is None:
            self._conn.execute(
                """
                INSERT INTO symbol_catalog (
                    symbol, provider, first_bar_ts, last_bar_ts,
                    archive_through, live_file, backfill_status, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sym,
                    provider or "",
                    first_bar_ts,
                    last_bar_ts,
                    archive_through,
                    live_file,
                    backfill_status or "pending",
                    now,
                ),
            )
        else:
            self._conn.execute(
                """
                UPDATE symbol_catalog SET
                    provider = COALESCE(?, provider),
                    first_bar_ts = COALESCE(?, first_bar_ts),
                    last_bar_ts = COALESCE(?, last_bar_ts),
                    archive_through = COALESCE(?, archive_through),
                    live_file = COALESCE(?, live_file),
                    backfill_status = COALESCE(?, backfill_status),
                    updated_at = ?
                WHERE symbol = ?
                """,
                (
                    provider,
                    first_bar_ts,
                    last_bar_ts,
                    archive_through,
                    live_file,
                    backfill_status,
                    now,
                    sym,
                ),
            )
        self._conn.commit()
        return self.get_symbol(sym)  # type: ignore[return-value]

    def update_bar_range(
        self,
        symbol: str,
        bars: list[Any],
        *,
        provider: str,
        live_file: str | None = None,
    ) -> None:
        if not bars:
            return
        timestamps = [int(b.bar_ts) for b in bars]
        first_ts = min(timestamps)
        last_ts = max(timestamps)
        entry = self.get_symbol(symbol)
        merged_first = first_ts
        merged_last = last_ts
        if entry and entry.first_bar_ts is not None:
            merged_first = min(merged_first, entry.first_bar_ts)
        if entry and entry.last_bar_ts is not None:
            merged_last = max(merged_last, entry.last_bar_ts)
        self.upsert_symbol(
            symbol,
            provider=provider,
            first_bar_ts=merged_first,
            last_bar_ts=merged_last,
            live_file=live_file,
        )

    def queue_backfill_job(self, symbol: str, year: int) -> None:
        now = int(time.time())
        self._conn.execute(
            """
            INSERT OR IGNORE INTO backfill_jobs (symbol, year, status, updated_at)
            VALUES (?, ?, 'queued', ?)
            """,
            (symbol.strip().upper(), year, now),
        )
        self._conn.commit()

    def get_pending_jobs(self, limit: int = 100) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """
            SELECT * FROM backfill_jobs
            WHERE status IN ('queued', 'failed')
            ORDER BY symbol, year
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]

    def set_job_status(
        self,
        symbol: str,
        year: int,
        status: str,
        *,
        provider: str | None = None,
        rows_written: int | None = None,
        error: str | None = None,
    ) -> None:
        now = int(time.time())
        self._conn.execute(
            """
            UPDATE backfill_jobs SET
                status = ?,
                provider = COALESCE(?, provider),
                rows_written = COALESCE(?, rows_written),
                error = ?,
                updated_at = ?
            WHERE symbol = ? AND year = ?
            """,
            (status, provider, rows_written, error, now, symbol.strip().upper(), year),
        )
        self._conn.commit()

    def log_ingest(
        self,
        symbol: str,
        *,
        bars_added: int,
        from_ts: int | None,
        to_ts: int | None,
        ok: bool,
        error: str | None = None,
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO ingest_log (symbol, run_at, bars_added, from_ts, to_ts, ok, error)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                symbol.strip().upper(),
                int(time.time()),
                bars_added,
                from_ts,
                to_ts,
                1 if ok else 0,
                error,
            ),
        )
        self._conn.commit()

    @staticmethod
    def _row_to_entry(row: sqlite3.Row) -> SymbolCatalogEntry:
        return SymbolCatalogEntry(
            symbol=row["symbol"],
            provider=row["provider"] or "",
            interval=row["interval"] or "1m",
            first_bar_ts=row["first_bar_ts"],
            last_bar_ts=row["last_bar_ts"],
            archive_through=row["archive_through"],
            live_file=row["live_file"],
            backfill_status=row["backfill_status"] or "pending",
            updated_at=row["updated_at"] or 0,
        )


def open_catalog_db(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn
