"""Realized-trade PnL attribution -- Phase 7's first real input into this angle.

Deviates from the standard bars-driven angle pattern (see spec.yaml): its natural input is
Phase 6 execution logs (closed positions), not price bars. `aggregate_pnl_attribution` is the
real, pure aggregation function -- called directly by `pnl_attribution_ingest.py` when new
closed positions are pushed. `compute()` keeps the standard runner signature so a generic
`/run/{ticker}` sweep across all angles doesn't error, but has nothing to compute from bars
alone, so it's a documented no-op.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats as _stats


def _rate_with_ci(values: list[float]) -> dict[str, Any]:
    """Mean + sample size + 95% CI, matching shock_personality's confidence-scored-fact shape."""
    n = len(values)
    if n < 2:
        return {
            "mean": float(np.mean(values)) if values else None,
            "n_observations": n,
            "confidence_interval": None,
            "status": "insufficient_sample" if n < 2 else "ok",
        }
    mean = float(np.mean(values))
    se = float(np.std(values, ddof=1) / np.sqrt(n))
    ci = _stats.t.interval(0.95, df=n - 1, loc=mean, scale=se)
    return {
        "mean": mean,
        "n_observations": n,
        "confidence_interval": [float(ci[0]), float(ci[1])],
        "status": "ok",
    }


def aggregate_pnl_attribution(
    symbol: str,
    closed_positions: list[dict[str, Any]],
) -> pd.DataFrame:
    """Aggregate a symbol's closed positions into win-rate/avg-win/avg-loss stats.

    `closed_positions` items are expected to carry at least `realized_pnl`, `avg_entry`,
    `qty` (matching `vinu_live.book.positions.list_closed_positions`'s row shape) -- extra
    keys are ignored, so the same dicts vinu-live's book already produces can be passed
    through unmodified.
    """
    analysis_at = datetime.now(timezone.utc).isoformat()

    if not closed_positions:
        return pd.DataFrame([{
            "symbol": symbol,
            "analysis_at": analysis_at,
            "angle": "pnl_attribution",
            "status": "no_data",
            "closed_positions_json": "[]",
        }])

    pnl_pcts: list[float] = []
    realized_pnls: list[float] = []
    for p in closed_positions:
        realized = float(p.get("realized_pnl", 0.0) or 0.0)
        realized_pnls.append(realized)
        cost = abs(float(p.get("avg_entry", 0.0) or 0.0) * float(p.get("qty", 0.0) or 0.0))
        pnl_pcts.append(realized / cost if cost > 0 else 0.0)

    wins = [p for p in pnl_pcts if p > 0]
    losses = [p for p in pnl_pcts if p <= 0]
    win_flags = [1.0 if p > 0 else 0.0 for p in pnl_pcts]

    result = {
        "symbol": symbol,
        "analysis_at": analysis_at,
        "angle": "pnl_attribution",
        "status": "ok",
        "n_trades": len(closed_positions),
        "total_realized_pnl": float(sum(realized_pnls)),
        "win_rate": _rate_with_ci(win_flags),
        "avg_win_pct": _rate_with_ci(wins),
        "avg_loss_pct": _rate_with_ci(losses),
        # Full history carried forward (as a JSON string, not a raw list column -- parquet
        # round-trips list-of-dicts columns as numpy object arrays, which FastAPI's JSON
        # encoder can't serialize when this row is later returned from /angle/{name}/{ticker})
        # so the next ingest can re-aggregate over everything, not just the newly-pushed
        # batch -- see pnl_attribution_ingest.py.
        "closed_positions_json": json.dumps(closed_positions),
    }
    return pd.DataFrame([result])


def compute(
    symbol: str,
    bars: pd.DataFrame | None = None,
    news: list[dict] | None = None,
    from_ts: int | None = None,
    to_ts: int | None = None,
    time_format: str | None = None,
) -> pd.DataFrame:
    """Standard runner signature -- a documented no-op. Real population is push-fed via
    `pnl_attribution_ingest.ingest_closed_positions`, not this bars-driven entry point.
    """
    return pd.DataFrame([{
        "symbol": symbol,
        "analysis_at": datetime.now(timezone.utc).isoformat(),
        "angle": "pnl_attribution",
        "status": "push_fed_not_runner_driven",
    }])
