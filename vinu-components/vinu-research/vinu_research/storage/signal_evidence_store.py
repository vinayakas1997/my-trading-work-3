"""Signal evidence store -- Phase 2 of the "must-condition + supporting-
indicator evidence" design (missing-pieces-of-system/new-theory-of-
trading/00-explanation.md), storage per Decisions 1, 2, 3, 7, 8 of that
folder's 01-planning.md.

Lives in vinu-research (Decision 8), not a new standalone service, for
the same reason judgment_store/HypothesisRegistry/CalibrationTracker
already live here: it's the same kind of evidence-recording concern, and
this is the one service that already owns the sweep_grid/walk-forward/
PBO machinery Layer 4's future analysis will reuse.

Two tables, not one:
- `signal_triggers`: one row per must-condition firing. Written once at
  trigger time with the outcome fields NULL (Decision 1: the full
  outcome path -- max favorable/adverse excursion, return-at-horizon --
  isn't known until the recording horizon has actually elapsed), then
  updated exactly once via `record_outcome()` once it has.
- `signal_evidence_indicators`: one row per (trigger, indicator) pair,
  each `indicator_data` a JSON blob holding that indicator's own natural
  output shape (Decision 3 -- shock_personality's flat dict, chronos's
  forecast-plus-metadata dict, a plain technical indicator's single
  value, all stored as-is, no flattening). This is the real-schema
  realization of "one JSON column per indicator": SQLite doesn't have
  dynamic columns, so a narrow child table keyed by indicator_name
  achieves the identical property Decision 3 actually cares about --
  heterogeneous shapes, zero schema change when an indicator's fields
  change or a new indicator is added -- without an ALTER TABLE per
  indicator.

No bucketing, no thresholds, no derived columns anywhere in this module
-- per Decision 1, that's the analysis layer's job (not yet built, see
02-implementation-status.md's Phase 3), not storage's.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from vinu_infra.sqlite import SQLiteBackend

SCHEMA = """
CREATE TABLE IF NOT EXISTS signal_triggers (
    trigger_id                  TEXT PRIMARY KEY,
    symbol                      TEXT NOT NULL,
    trigger_time                TEXT NOT NULL,
    must_condition              TEXT NOT NULL,
    granularity                 TEXT NOT NULL DEFAULT '15min',
    policy_version              TEXT,
    max_favorable_excursion     REAL,
    max_adverse_excursion       REAL,
    return_at_horizon           REAL,
    outcome_recorded_at         TEXT,
    created_at                  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_signal_triggers_symbol ON signal_triggers(symbol);
CREATE INDEX IF NOT EXISTS idx_signal_triggers_unresolved
    ON signal_triggers(outcome_recorded_at) WHERE outcome_recorded_at IS NULL;

CREATE TABLE IF NOT EXISTS signal_evidence_indicators (
    trigger_id      TEXT NOT NULL REFERENCES signal_triggers(trigger_id),
    indicator_name  TEXT NOT NULL,
    indicator_data  TEXT NOT NULL,
    PRIMARY KEY (trigger_id, indicator_name)
);
CREATE INDEX IF NOT EXISTS idx_evidence_indicator_name ON signal_evidence_indicators(indicator_name);
"""


class SignalEvidenceStore(SQLiteBackend):
    SCHEMA = SCHEMA
    SCHEMA_VERSION = 1

    def record_trigger(
        self,
        trigger_id: str,
        symbol: str,
        trigger_time: str,
        must_condition: str | list[str],
        indicators: dict[str, Any],
        *,
        granularity: str = "15min",
        policy_version: str | None = None,
    ) -> None:
        """Write one trigger row plus its full raw indicator snapshot.

        `must_condition` is a single condition name or a list (Decision 1
        note: a strategy can have more than one must-condition; all that
        fired together are recorded, joined as JSON). `indicators` maps
        indicator/angle name -> its own natural output (dict, list,
        scalar, whatever that indicator produces) -- stored one row per
        key in `signal_evidence_indicators`, each value JSON-serialized
        as-is, no reshaping.
        """
        conn = self._get_conn()
        now = datetime.now(timezone.utc).isoformat()
        must_condition_json = json.dumps(
            must_condition if isinstance(must_condition, list) else [must_condition]
        )
        conn.execute(
            """INSERT INTO signal_triggers
               (trigger_id, symbol, trigger_time, must_condition, granularity,
                policy_version, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (trigger_id, symbol, trigger_time, must_condition_json, granularity, policy_version, now),
        )
        for indicator_name, indicator_value in indicators.items():
            conn.execute(
                """INSERT OR REPLACE INTO signal_evidence_indicators
                   (trigger_id, indicator_name, indicator_data)
                   VALUES (?, ?, ?)""",
                (trigger_id, indicator_name, json.dumps(indicator_value, default=str)),
            )
        conn.commit()

    def record_outcome(
        self,
        trigger_id: str,
        *,
        max_favorable_excursion: float,
        max_adverse_excursion: float,
        return_at_horizon: float,
    ) -> None:
        """Fill in the outcome path once the recording horizon has actually
        elapsed for this trigger. Idempotent-by-overwrite -- calling this
        again for the same trigger_id (e.g. a horizon re-measured with a
        longer window later) replaces the previous outcome rather than
        erroring, since Decision 1 explicitly allows the horizon question
        to be revisited without needing to re-record the trigger itself."""
        conn = self._get_conn()
        conn.execute(
            """UPDATE signal_triggers
               SET max_favorable_excursion = ?,
                   max_adverse_excursion = ?,
                   return_at_horizon = ?,
                   outcome_recorded_at = ?
               WHERE trigger_id = ?""",
            (
                max_favorable_excursion,
                max_adverse_excursion,
                return_at_horizon,
                datetime.now(timezone.utc).isoformat(),
                trigger_id,
            ),
        )
        conn.commit()

    def get_trigger(self, trigger_id: str) -> dict[str, Any] | None:
        """The full row plus every recorded indicator's raw value, nested
        under `indicators` -- the shape Layer 4's future analysis would
        actually read (Decision 3: no flattening done here, JSON parsed
        back into its original structure per indicator)."""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM signal_triggers WHERE trigger_id = ?", (trigger_id,)
        ).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["must_condition"] = json.loads(result["must_condition"])
        indicator_rows = conn.execute(
            "SELECT indicator_name, indicator_data FROM signal_evidence_indicators WHERE trigger_id = ?",
            (trigger_id,),
        ).fetchall()
        result["indicators"] = {r["indicator_name"]: json.loads(r["indicator_data"]) for r in indicator_rows}
        return result

    def list_triggers(self, symbol: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        """Metadata rows only (no indicator join) -- for browsing/counting;
        use get_trigger() for the full evidence row including indicators."""
        conn = self._get_conn()
        query = "SELECT * FROM signal_triggers WHERE 1=1"
        params: list[Any] = []
        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)
        query += " ORDER BY trigger_time DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(query, params).fetchall()
        results = []
        for row in rows:
            d = dict(row)
            d["must_condition"] = json.loads(d["must_condition"])
            results.append(d)
        return results

    def get_unresolved_triggers(self, older_than_iso: str, limit: int = 200) -> list[dict[str, Any]]:
        """Triggers whose outcome horizon has plausibly elapsed by now but
        whose outcome was never recorded -- the query whatever job ends up
        computing outcomes (not built yet, see 02-implementation-status.md)
        would poll to find its work. `older_than_iso` is the caller's own
        "trigger_time + horizon <= now" cutoff, computed by the caller
        (this store doesn't know what horizon any given must-condition
        uses -- Decision 1/8's whole point is that horizon is an
        analysis-time question, not a storage-time constant)."""
        conn = self._get_conn()
        rows = conn.execute(
            """SELECT * FROM signal_triggers
               WHERE outcome_recorded_at IS NULL AND trigger_time <= ?
               ORDER BY trigger_time ASC LIMIT ?""",
            (older_than_iso, limit),
        ).fetchall()
        results = []
        for row in rows:
            d = dict(row)
            d["must_condition"] = json.loads(d["must_condition"])
            results.append(d)
        return results
