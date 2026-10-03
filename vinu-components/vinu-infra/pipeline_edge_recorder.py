"""Runtime recorder for the pipeline edge manifest -- Phase 3 of
newer-thinking-with-discussed/the-inconsistencies-v2/03-implementation-plan.md.

`pipeline_edges.yaml` says WHAT should flow where; its static check proves a
consumer *references* its producer. This module records what actually
happened at runtime, at each instrumented consumption point:

    received  -- the input arrived and was usable
    empty     -- it arrived but was legitimately/unexpectedly empty
    stale     -- it arrived but older than the consumer tolerates
    missing   -- it did not arrive (fetch failed, producer not running)

One small row per edge (latest status, counters, first/last timestamps) plus a
change log that only grows when the status CHANGES -- so a healthy edge costs
one tiny upsert per observation and zero log rows, and "when did this stop
flowing" is answerable from the log.

Hard rules (this sits next to order flow):
* `record_edge` NEVER raises and never blocks on anything but one local SQLite
  write. Every failure is swallowed (debug-logged).
* It is observe-only: nothing reads these rows to make a trading decision.
* No configured data root -> a silent no-op, so a service without the shared
  mount behaves exactly as before.

What it cannot tell you: that a value that DID arrive is correct. It reports
presence and age, not correctness.
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any

from vinu_infra.sqlite import SQLiteBackend

LOG = logging.getLogger(__name__)

STATUSES = ("received", "empty", "stale", "missing")
_MAX_EVENTS_PER_EDGE = 200

_SCHEMA = """
CREATE TABLE IF NOT EXISTS edge_state (
    edge_id      TEXT PRIMARY KEY,
    status       TEXT NOT NULL,
    first_seen   REAL NOT NULL,
    last_seen    REAL NOT NULL,
    last_ok      REAL,
    last_change  REAL NOT NULL,
    n_received   INTEGER NOT NULL DEFAULT 0,
    n_empty      INTEGER NOT NULL DEFAULT 0,
    n_stale      INTEGER NOT NULL DEFAULT 0,
    n_missing    INTEGER NOT NULL DEFAULT 0,
    last_detail  TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS edge_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    edge_id     TEXT NOT NULL,
    ts          REAL NOT NULL,
    from_status TEXT,
    to_status   TEXT NOT NULL,
    detail      TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_edge_events_edge ON edge_events(edge_id, id);
"""


class EdgeStatusStore(SQLiteBackend):
    SCHEMA = _SCHEMA
    SCHEMA_VERSION = 1

    def __init__(self, path: Path | str | None = None) -> None:
        super().__init__(path if path else ":memory:")

    def record(self, edge_id: str, status: str, detail: str = "", *, now: float | None = None) -> None:
        if status not in STATUSES:
            raise ValueError(f"status must be one of {STATUSES}, got {status!r}")
        now = now if now is not None else time.time()
        detail = (detail or "")[:500]
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM edge_state WHERE edge_id = ?", (edge_id,)).fetchone()
        if row is None:
            conn.execute(
                """INSERT INTO edge_state (edge_id, status, first_seen, last_seen, last_ok, last_change,
                       n_received, n_empty, n_stale, n_missing, last_detail)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    edge_id, status, now, now, now if status == "received" else None, now,
                    int(status == "received"), int(status == "empty"),
                    int(status == "stale"), int(status == "missing"), detail,
                ),
            )
            conn.execute(
                "INSERT INTO edge_events (edge_id, ts, from_status, to_status, detail) VALUES (?, ?, NULL, ?, ?)",
                (edge_id, now, status, detail),
            )
        else:
            changed = row["status"] != status
            conn.execute(
                f"""UPDATE edge_state SET status = ?, last_seen = ?,
                       last_ok = CASE WHEN ? = 'received' THEN ? ELSE last_ok END,
                       last_change = CASE WHEN ? THEN ? ELSE last_change END,
                       n_{status} = n_{status} + 1, last_detail = ?
                    WHERE edge_id = ?""",
                (status, now, status, now, int(changed), now, detail, edge_id),
            )
            if changed:
                conn.execute(
                    "INSERT INTO edge_events (edge_id, ts, from_status, to_status, detail) VALUES (?, ?, ?, ?, ?)",
                    (edge_id, now, row["status"], status, detail),
                )
                conn.execute(
                    """DELETE FROM edge_events WHERE edge_id = ? AND id NOT IN (
                           SELECT id FROM edge_events WHERE edge_id = ? ORDER BY id DESC LIMIT ?)""",
                    (edge_id, edge_id, _MAX_EVENTS_PER_EDGE),
                )
        conn.commit()

    def get_state(self, edge_id: str) -> dict[str, Any] | None:
        row = self._get_conn().execute("SELECT * FROM edge_state WHERE edge_id = ?", (edge_id,)).fetchone()
        return dict(row) if row else None

    def list_states(self) -> list[dict[str, Any]]:
        rows = self._get_conn().execute("SELECT * FROM edge_state ORDER BY edge_id").fetchall()
        return [dict(r) for r in rows]

    def list_events(self, edge_id: str, limit: int = 50) -> list[dict[str, Any]]:
        rows = self._get_conn().execute(
            "SELECT * FROM edge_events WHERE edge_id = ? ORDER BY id DESC LIMIT ?", (edge_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]


# ------------------------------------------------------------------ module-level, never-raising helper

_stores: dict[str, EdgeStatusStore] = {}


def _resolve_root() -> Path | None:
    """VINU_EDGE_DATA_ROOT, else the evaluation data root research / live / agent already share
    (VINU_STRATEGY_EVAL_DATA_ROOT). None -> recording is a silent no-op."""
    for var in ("VINU_EDGE_DATA_ROOT", "VINU_STRATEGY_EVAL_DATA_ROOT"):
        v = os.environ.get(var, "").strip()
        if v:
            return Path(v)
    return None


def resolve_edge_status_store(fallback_root: Path | str | None = None) -> EdgeStatusStore | None:
    """The shared store for the configured root, or for `fallback_root` when no env root is set.
    Cached per path. None when neither exists."""
    root = _resolve_root() or (Path(fallback_root) if fallback_root else None)
    if root is None:
        return None
    path = str(root / "pipeline_edges.db")
    store = _stores.get(path)
    if store is None:
        store = EdgeStatusStore(path)
        _stores[path] = store
    return store


def record_edge(edge_id: str, status: str, detail: str = "", *, store: EdgeStatusStore | None = None) -> None:
    """Record one observation. NEVER raises, never blocks beyond a local SQLite write.
    An unknown status or any storage failure is swallowed and debug-logged."""
    try:
        target = store if store is not None else resolve_edge_status_store()
        if target is None:
            return
        target.record(edge_id, status, detail)
    except Exception as exc:  # noqa: BLE001 -- observe-only; must never touch the caller
        LOG.debug("record_edge(%s, %s) failed: %s", edge_id, status, exc)


def reset_for_tests() -> None:
    """Drop cached stores (tests only)."""
    for s in _stores.values():
        try:
            s.close()
        except Exception:  # noqa: BLE001
            pass
    _stores.clear()


# ------------------------------------------------------------------ the "what is not flowing" view

HEALTHY_STATES = {"flowing", "known_gap", "not_instrumented", "recording_disabled"}


def edges_flow_report(
    edges: list[Any], store: EdgeStatusStore | None, *, now: float | None = None,
) -> list[dict[str, Any]]:
    """One row per manifest edge, merged with what was actually recorded.

    state:
      known_gap         manifest says this connection is not wired yet -- not expected to flow
      not_instrumented  no recording call site yet, so absence of data says nothing
      never_seen        instrumented but nothing has ever been recorded (producer or consumer never ran)
      recording_disabled  instrumented, but no shared recording root is configured, so silence says nothing
      flowing           last observation was `received` (or `empty` where the edge allows empty) and is fresh
      empty             last observation was empty on an edge that should not be empty
      stale             the last observation is older than the edge's `stale_after_sec`
      missing           the last observation was a failure to receive
    """
    now = now if now is not None else time.time()
    states = {s["edge_id"]: s for s in (store.list_states() if store is not None else [])}
    rows: list[dict[str, Any]] = []
    for e in edges:
        base = {
            "edge_id": e.id, "manifest_status": e.status, "gap_ref": e.gap_ref,
            "purpose": e.purpose, "instrumented": bool(getattr(e, "instrumented", False)),
        }
        st = states.get(e.id)
        if e.status == "gap":
            rows.append({**base, "state": "known_gap"})
            continue
        if not base["instrumented"] and st is None:
            rows.append({**base, "state": "not_instrumented"})
            continue
        if st is None:
            rows.append({**base, "state": "never_seen" if store is not None else "recording_disabled"})
            continue
        age = now - st["last_seen"]
        stale_after = getattr(e, "stale_after_sec", None)
        last = st["status"]
        if last == "missing":
            state = "missing"
        elif last == "stale" or (stale_after is not None and age > stale_after):
            state = "stale"
        elif last == "empty" and not e.empty_ok:
            state = "empty"
        else:
            state = "flowing"
        rows.append({
            **base, "state": state, "last_status": last, "last_detail": st["last_detail"],
            "last_seen_age_sec": round(age, 1),
            "last_ok_age_sec": None if st["last_ok"] is None else round(now - st["last_ok"], 1),
            "since_age_sec": round(now - st["last_change"], 1),
            "counts": {k: st[f"n_{k}"] for k in STATUSES},
        })
    return rows


def not_flowing(report: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The subset of a report that needs attention."""
    return [r for r in report if r["state"] not in HEALTHY_STATES]
