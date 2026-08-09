"""drawdown_deep_dive's own detection-run glue code.

Not a forecaster and not even a fixed-cadence rolling scan (Group B, per
06-implementation-of-each-angles/Agents.md) -- detect_drawdown_episodes()
(drawdown.py) is a state machine over the whole bars series that emits a
variable number of episode rows, so this doesn't use run_walk_forward at
all. No weights store: nothing is trained.
"""

from __future__ import annotations

import pandas as pd

from vinu_initial_analysis.angles._tagging import tag_row
from vinu_initial_analysis.angles.drawdown_deep_dive.drawdown import detect_drawdown_episodes

# Decided default (04-enhancement-of-each-angle/06-drawdown_deep_dive.md SS3).
DEFAULT_K = 2.0
# The robustness sweep the design doc's own "Open/unresolved" flagged as
# not yet actually run.
K_SWEEP = (1.5, 2.0, 2.5, 3.0)


def run_drawdown_detection(
    symbol: str,
    timeframe: str,
    bars: pd.DataFrame,
    news: list[dict] | None = None,
    k: float = DEFAULT_K,
) -> pd.DataFrame:
    """One tagged row per detected episode (by peak_ts), for a single k."""
    episodes = detect_drawdown_episodes(symbol, bars, k, news=news)
    rows = []
    for idx, ep in enumerate(episodes):
        row = {
            "symbol": symbol,
            "timeframe": timeframe,
            "bar_ts": ep["peak_ts"],  # tagged by peak_ts, per the decided design
            "episode_index": idx,
            "k": k,
        }
        row.update(tag_row(ep["peak_ts"]))
        row.update(ep)
        rows.append(row)
    return pd.DataFrame(rows)


def run_k_sweep(
    symbol: str,
    timeframe: str,
    bars: pd.DataFrame,
    news: list[dict] | None = None,
    k_values: tuple[float, ...] = K_SWEEP,
) -> pd.DataFrame:
    """Runs detection once per k in k_values; one summary row per k so
    stability across the sweep is a real, measured comparison, not assumed.
    """
    rows = []
    for k in k_values:
        df = run_drawdown_detection(symbol, timeframe, bars, news=news, k=k)
        recovered = df[df["status"] == "recovered"] if len(df) else df
        rows.append({
            "symbol": symbol,
            "timeframe": timeframe,
            "k": k,
            "n_episodes": len(df),
            "n_recovered": len(recovered),
            "n_open": len(df) - len(recovered),
            "avg_drop_pct": round(df["drop_pct"].mean(), 4) if len(df) else None,
            "avg_duration_to_trough": round(df["duration_to_trough"].mean(), 2) if len(df) else None,
            "avg_duration_to_recovery": round(recovered["duration_to_recovery"].mean(), 2) if len(recovered) else None,
        })
    return pd.DataFrame(rows)
