"""Quote spreads by session: the measurement the backtest cost multipliers were guessed without (problem log O10).

The ingest loop takes a few quote snapshots every cycle, in every session, and files each under the session it was taken in.
`stats()` gives the median and 90th-percentile spread per session; `suggested_multipliers()` turns those into the factors
`VINU_SIM_SESSION_COST_MULT` expects (a session's median spread over the regular session's, never below 1), but only for a
session with at least MIN_SAMPLES snapshots: below that it says nothing rather than guess.
"""
from __future__ import annotations

import time
from typing import Any

from vinu_infra.sessions import REGULAR, TRADABLE_SESSIONS, session_of
from vinu_infra.sqlite import SQLiteBackend

MIN_SAMPLES = 30


class SpreadStore(SQLiteBackend):
    SCHEMA = """
    CREATE TABLE IF NOT EXISTS spread_snapshots (
        ts         REAL NOT NULL,
        symbol     TEXT NOT NULL,
        session    TEXT NOT NULL,
        bid        REAL,
        ask        REAL,
        mid        REAL,
        spread_bps REAL NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_spread_session_ts ON spread_snapshots (session, ts);
    """
    SCHEMA_VERSION = 1

    def record(self, symbol: str, quote: dict[str, Any], *, now: float | None = None) -> bool:
        """File one quote payload (the /stock/quote shape). Returns False, writing nothing, when it has no usable spread."""
        try:
            spread = float(quote.get("spread_bps"))
        except (TypeError, ValueError):
            return False
        if not quote.get("ok") or spread < 0:
            return False
        ts = time.time() if now is None else now
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO spread_snapshots (ts, symbol, session, bid, ask, mid, spread_bps) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (ts, symbol.upper(), session_of(ts), quote.get("bid"), quote.get("ask"), quote.get("mid"), spread),
        )
        conn.commit()
        return True

    def stats(self, days: float = 30.0, *, now: float | None = None) -> dict[str, dict[str, Any]]:
        since = (time.time() if now is None else now) - days * 86400.0
        conn = self._get_conn()
        out: dict[str, dict[str, Any]] = {}
        for session in TRADABLE_SESSIONS:
            vals = sorted(r[0] for r in conn.execute(
                "SELECT spread_bps FROM spread_snapshots WHERE session = ? AND ts >= ?", (session, since)).fetchall())
            n = len(vals)
            out[session] = {
                "snapshots": n,
                "median_bps": vals[n // 2] if n % 2 else (vals[n // 2 - 1] + vals[n // 2]) / 2 if n else None,
                "p90_bps": vals[min(n - 1, int(n * 0.9))] if n else None,
            }
        return out

    def suggested_multipliers(self, days: float = 30.0, *, now: float | None = None) -> dict[str, float | None]:
        """Per session: median spread over the regular session's median (at least 1), or None when either side has fewer
        than MIN_SAMPLES snapshots."""
        s = self.stats(days, now=now)
        base = s[REGULAR]
        out: dict[str, float | None] = {}
        for session in TRADABLE_SESSIONS:
            enough = s[session]["snapshots"] >= MIN_SAMPLES and base["snapshots"] >= MIN_SAMPLES and base["median_bps"]
            out[session] = max(1.0, round(s[session]["median_bps"] / base["median_bps"], 2)) if enough else None
        return out
