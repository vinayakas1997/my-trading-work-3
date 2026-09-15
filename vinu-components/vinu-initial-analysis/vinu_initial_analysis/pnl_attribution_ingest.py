"""Phase 7 ingest path for the push-fed `pnl_attribution` angle (see angles/pnl_attribution/).

Called from a new HTTP endpoint (`POST /pnl-attribution/{symbol}/record`), itself called by
vinu-live's feedback loop whenever a Phase 6 trade-plan position closes -- never by the
bars-driven `AngleRunner`.
"""

from __future__ import annotations

import json
import time
from typing import Any

from vinu_initial_analysis.angles.pnl_attribution.compute import aggregate_pnl_attribution
from vinu_initial_analysis.storage.parquet import AngleStorage


def ingest_closed_positions(
    storage: AngleStorage,
    symbol: str,
    closed_positions: list[dict[str, Any]],
    *,
    run_log: Any = None,
) -> str:
    """Merge newly-pushed closed positions with prior history and re-store the aggregated
    pnl_attribution angle. Returns the new run_id.

    Dedupes by `position_id` so re-delivery of the same closed position (e.g. a retried
    feedback-loop cycle) never double-counts it.

    `run_log`, when given, gets a `record_run` row for this ingest -- this push-fed path
    used to be the only write into AngleStorage that never touched RunLog at all (every
    bars-driven angle run in runner.py does), so nothing driven off RunLog (admin purge,
    run-status lookups, a future narrator asking "when was this angle last updated, did
    it error") could ever see a pnl_attribution ingest event. Best-effort: a RunLog write
    failure must never break the actual data write, which already succeeded above.
    """
    symbol = symbol.upper()
    t0 = time.perf_counter()
    prior_positions = _extract_prior_positions(storage.read_latest(symbol, "pnl_attribution"))

    by_id: dict[str, dict[str, Any]] = {
        p["position_id"]: p for p in prior_positions if p.get("position_id")
    }
    unkeyed = [p for p in prior_positions if not p.get("position_id")]
    for p in closed_positions:
        pid = p.get("position_id", "")
        if pid:
            by_id[pid] = p
        else:
            unkeyed.append(p)

    combined = list(by_id.values()) + unkeyed
    result_df = aggregate_pnl_attribution(symbol, combined)
    run_id = storage.write(symbol, "pnl_attribution", result_df)

    if run_log is not None:
        try:
            run_log.record_run(
                symbol=symbol,
                angle_name="pnl_attribution",
                run_id=run_id,
                row_count=len(result_df),
                duration_seconds=time.perf_counter() - t0,
                granularity="event",
            )
        except Exception:
            pass

    return run_id


def _extract_prior_positions(prior_df: Any) -> list[dict[str, Any]]:
    if prior_df is None or prior_df.empty:
        return []
    raw = prior_df.iloc[-1].get("closed_positions_json")
    if not raw:
        return []
    return json.loads(raw)
