"""backtesting_44_metrics' own rolling-window computation glue code.

Not a forecaster (Group B, per 06-implementation-of-each-angles/Agents.md)
-- there is nothing to predict or check against a future bar, so this
doesn't use the walk-forward harness's step_fn/future contract. Instead:
a rolling trailing window of returns at each step produces one tagged row
of the 11 "core" metrics (Layer 1 raw material for later session/day/week
aggregation, per 04-enhancement-of-each-angle/02-backtesting_44_metrics.md
SS5). The 6 whole-history-only metrics are computed once, separately,
never tagged or sliced -- per that same decided design.
"""

from __future__ import annotations

import pandas as pd

from vinu_initial_analysis.angles._tagging import tag_row
from vinu_initial_analysis.angles.backtesting_44_metrics.compute import (
    _core_metrics,
    _whole_history_metrics,
)

# Extends the project's established N=100 convention (ARIMA/DLinear) --
# not explicitly pinned in this angle's own design doc, see 00-plan.md.
MIN_OBSERVATIONS = 100


def run_core_metrics_backtest(symbol: str, timeframe: str, bars: pd.DataFrame) -> pd.DataFrame:
    """One tagged row per step: the 11 core metrics computed over a
    trailing MIN_OBSERVATIONS-sized window of returns ending at that bar.
    """
    close = bars["close"].astype(float).values
    bar_ts_all = bars["bar_ts"].astype(int).values
    rets = pd.Series(close).pct_change().values[1:]
    ts = bar_ts_all[1:]

    rows = []
    for i in range(MIN_OBSERVATIONS - 1, len(rets)):
        window = rets[i - MIN_OBSERVATIONS + 1 : i + 1]
        bar_ts = int(ts[i])
        row = {
            "symbol": symbol,
            "timeframe": timeframe,
            "bar_ts": bar_ts,
            "step_index": i - (MIN_OBSERVATIONS - 1),
        }
        row.update(tag_row(bar_ts))
        row.update(_core_metrics(window, timeframe))
        rows.append(row)
    return pd.DataFrame(rows)


def run_whole_history_metrics(symbol: str, timeframe: str, bars: pd.DataFrame) -> pd.DataFrame:
    """The 6 tail-risk/distribution-shape metrics, computed once over the
    full history, never tagged or sliced -- stored separately, per the
    decided design.
    """
    close = bars["close"].astype(float)
    rets = close.pct_change().dropna().values
    row = {"symbol": symbol, "timeframe": timeframe}
    row.update(_whole_history_metrics(rets))
    return pd.DataFrame([row])
