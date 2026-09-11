"""Persisted rule storage -- the "wire it up" piece Stage B was explicitly
left without: `ScanRule`/`ScanMonitor`/`FilterChain`/the pipeline were all
built and tested, but nothing kept a rule around between process restarts,
and nothing decided *which* rules to run. `RuleStore` is that: CRUD +
enable/disable for `ScanRule`s, SQLite-backed with the same
`SQLiteBackend` convention every other Vina store in this session uses.

Deliberately still decoupled per B15: this module knows nothing about
`vinu-agent`/`vinu-live`/`vinu-research` -- it stores and returns
`ScanRule` objects and nothing else.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass

from vinu_infra.sqlite import SQLiteBackend

from ..scan.monitor import MIN_INTERVAL_SEC, ScanRule

SCHEMA = """
CREATE TABLE IF NOT EXISTS rules (
    rule_id      TEXT PRIMARY KEY,
    rule_json    TEXT NOT NULL,
    interval_sec REAL NOT NULL DEFAULT 60.0,
    active       INTEGER NOT NULL DEFAULT 1,
    created_at   REAL NOT NULL,
    updated_at   REAL NOT NULL
);
"""


@dataclass(frozen=True)
class StoredRule:
    rule: ScanRule
    interval_sec: float
    active: bool
    created_at: float
    updated_at: float

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule.rule_id,
            "condition": self.rule.condition.to_dict(),
            "universe": list(self.rule.universe),
            "cooldown_min": self.rule.cooldown_min,
            "coarse_filter": asdict(self.rule.coarse_filter),
            "actions": self.rule.actions.to_dict(),
            "mode": self.rule.mode,
            "interval_sec": self.interval_sec,
            "active": self.active,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


def _rule_to_json(rule: ScanRule) -> str:
    return json.dumps({
        "rule_id": rule.rule_id,
        "condition": rule.condition.to_dict(),
        "universe": list(rule.universe),
        "cooldown_min": rule.cooldown_min,
        "coarse_filter": asdict(rule.coarse_filter),
        "actions": rule.actions.to_dict(),
        "mode": rule.mode,
    })


def _row_to_stored(row) -> StoredRule:
    raw = json.loads(row["rule_json"])
    rule = ScanRule.from_dict(raw)
    return StoredRule(rule, float(row["interval_sec"]), bool(row["active"]), float(row["created_at"]), float(row["updated_at"]))


class RuleStore(SQLiteBackend):
    SCHEMA = SCHEMA
    SCHEMA_VERSION = 1

    def upsert_rule(self, rule: ScanRule, *, interval_sec: float = 60.0, active: bool = True) -> StoredRule:
        # Same rate-limit floor as ScanMonitor's own interval_sec -- a rule
        # stored (and later scheduled) below MIN_INTERVAL_SEC must not be
        # able to bypass it just because it came in through the store
        # instead of ScanMonitor's constructor.
        interval_sec = max(interval_sec, MIN_INTERVAL_SEC)
        now = time.time()
        conn = self._get_conn()
        existing = conn.execute("SELECT created_at FROM rules WHERE rule_id = ?", (rule.rule_id,)).fetchone()
        created_at = float(existing["created_at"]) if existing is not None else now
        self.upsert(
            "rules",
            {
                "rule_id": rule.rule_id,
                "rule_json": _rule_to_json(rule),
                "interval_sec": interval_sec,
                "active": int(active),
                "created_at": created_at,
                "updated_at": now,
            },
            conflict_columns=["rule_id"],
        )
        return StoredRule(rule, interval_sec, active, created_at, now)

    def get(self, rule_id: str) -> StoredRule | None:
        row = self._get_conn().execute("SELECT * FROM rules WHERE rule_id = ?", (rule_id,)).fetchone()
        return _row_to_stored(row) if row is not None else None

    def all(self, *, active_only: bool = False) -> list[StoredRule]:
        sql = "SELECT * FROM rules" + (" WHERE active = 1" if active_only else "") + " ORDER BY rule_id"
        rows = self._get_conn().execute(sql).fetchall()
        return [_row_to_stored(r) for r in rows]

    def delete(self, rule_id: str) -> bool:
        conn = self._get_conn()
        cur = conn.execute("DELETE FROM rules WHERE rule_id = ?", (rule_id,))
        conn.commit()
        return cur.rowcount > 0

    def set_active(self, rule_id: str, active: bool) -> bool:
        """Used both by an operator (enable/disable) and by the scheduler
        itself for B18's one-shot deactivation (`CycleResult.deactivate_rule`)
        -- the same primitive serves both callers."""
        conn = self._get_conn()
        cur = conn.execute(
            "UPDATE rules SET active = ?, updated_at = ? WHERE rule_id = ?",
            (int(active), time.time(), rule_id),
        )
        conn.commit()
        return cur.rowcount > 0
