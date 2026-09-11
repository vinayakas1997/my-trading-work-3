"""Persisted `RankerConfig` CRUD + enable/disable -- the same `RuleStore`
pattern (`rules/store.py`), applied to rankers instead of condition rules.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass

from vinu_infra.sqlite import SQLiteBackend

from .config import RANKER_MIN_INTERVAL_SEC, ONE_DAY_SEC, RankerConfig

SCHEMA = """
CREATE TABLE IF NOT EXISTS rankers (
    ranker_id    TEXT PRIMARY KEY,
    ranker_json  TEXT NOT NULL,
    interval_sec REAL NOT NULL DEFAULT 86400.0,
    active       INTEGER NOT NULL DEFAULT 1,
    created_at   REAL NOT NULL,
    updated_at   REAL NOT NULL
);
"""


@dataclass(frozen=True)
class StoredRanker:
    ranker: RankerConfig
    interval_sec: float
    active: bool
    created_at: float
    updated_at: float

    def to_dict(self) -> dict:
        d = self.ranker.to_dict()
        d.update(interval_sec=self.interval_sec, active=self.active, created_at=self.created_at, updated_at=self.updated_at)
        return d


def _row_to_stored(row) -> StoredRanker:
    raw = json.loads(row["ranker_json"])
    return StoredRanker(
        RankerConfig.from_dict(raw), float(row["interval_sec"]), bool(row["active"]),
        float(row["created_at"]), float(row["updated_at"]),
    )


class RankerStore(SQLiteBackend):
    SCHEMA = SCHEMA
    SCHEMA_VERSION = 1

    def upsert_ranker(
        self, ranker: RankerConfig, *, interval_sec: float = ONE_DAY_SEC, active: bool = True,
    ) -> StoredRanker:
        interval_sec = max(interval_sec, RANKER_MIN_INTERVAL_SEC)
        now = time.time()
        conn = self._get_conn()
        existing = conn.execute("SELECT created_at FROM rankers WHERE ranker_id = ?", (ranker.ranker_id,)).fetchone()
        created_at = float(existing["created_at"]) if existing is not None else now
        self.upsert(
            "rankers",
            {
                "ranker_id": ranker.ranker_id,
                "ranker_json": json.dumps(ranker.to_dict()),
                "interval_sec": interval_sec,
                "active": int(active),
                "created_at": created_at,
                "updated_at": now,
            },
            conflict_columns=["ranker_id"],
        )
        return StoredRanker(ranker, interval_sec, active, created_at, now)

    def get(self, ranker_id: str) -> StoredRanker | None:
        row = self._get_conn().execute("SELECT * FROM rankers WHERE ranker_id = ?", (ranker_id,)).fetchone()
        return _row_to_stored(row) if row is not None else None

    def all(self, *, active_only: bool = False) -> list[StoredRanker]:
        sql = "SELECT * FROM rankers" + (" WHERE active = 1" if active_only else "") + " ORDER BY ranker_id"
        return [_row_to_stored(r) for r in self._get_conn().execute(sql).fetchall()]

    def delete(self, ranker_id: str) -> bool:
        conn = self._get_conn()
        cur = conn.execute("DELETE FROM rankers WHERE ranker_id = ?", (ranker_id,))
        conn.commit()
        return cur.rowcount > 0

    def set_active(self, ranker_id: str, active: bool) -> bool:
        conn = self._get_conn()
        cur = conn.execute(
            "UPDATE rankers SET active = ?, updated_at = ? WHERE ranker_id = ?",
            (int(active), time.time(), ranker_id),
        )
        conn.commit()
        return cur.rowcount > 0
