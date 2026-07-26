"""Phase 7 ingest path for the push-fed `pnl_attribution` angle (see angles/pnl_attribution/).

Called from a new HTTP endpoint (`POST /pnl-attribution/{symbol}/record`), itself called by
vinu-live's feedback loop whenever a Phase 6 trade-plan position closes -- never by the
bars-driven `AngleRunner`.
"""

from __future__ import annotations

import json
from typing import Any

from vinu_initial_analysis.angles.pnl_attribution.compute import aggregate_pnl_attribution
from vinu_initial_analysis.storage.parquet import AngleStorage


def ingest_closed_positions(
    storage: AngleStorage,
    symbol: str,
    closed_positions: list[dict[str, Any]],
) -> str:
    """Merge newly-pushed closed positions with prior history and re-store the aggregated
    pnl_attribution angle. Returns the new run_id.

    Dedupes by `position_id` so re-delivery of the same closed position (e.g. a retried
    feedback-loop cycle) never double-counts it.
    """
    symbol = symbol.upper()
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
    return storage.write(symbol, "pnl_attribution", result_df)


def _extract_prior_positions(prior_df: Any) -> list[dict[str, Any]]:
    if prior_df is None or prior_df.empty:
        return []
    raw = prior_df.iloc[-1].get("closed_positions_json")
    if not raw:
        return []
    return json.loads(raw)
