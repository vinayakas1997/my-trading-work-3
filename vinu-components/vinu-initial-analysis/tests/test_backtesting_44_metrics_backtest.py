from __future__ import annotations

import numpy as np
import pandas as pd

from vinu_initial_analysis.angles._tagging import tag_row
from vinu_initial_analysis.angles.backtesting_44_metrics.backtest import (
    MIN_OBSERVATIONS,
    run_core_metrics_backtest,
    run_whole_history_metrics,
)
from vinu_initial_analysis.angles.backtesting_44_metrics.compute import compute


def _make_bars(n: int, seed: int = 1) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(0, 0.5, size=n))
    bar_ts = list(range(1_700_000_000, 1_700_000_000 + n * 86400, 86400))
    return pd.DataFrame({"bar_ts": bar_ts, "close": close})


def test_core_metrics_row_count():
    bars = _make_bars(n=MIN_OBSERVATIONS + 20)
    df = run_core_metrics_backtest("AAPL", "1D", bars)
    # returns series is n-1 long; first MIN_OBSERVATIONS-1 consumed before first step
    assert len(df) == (len(bars) - 1) - (MIN_OBSERVATIONS - 1)


def test_core_metrics_rows_are_tagged_consistently():
    bars = _make_bars(n=MIN_OBSERVATIONS + 5)
    df = run_core_metrics_backtest("AAPL", "1D", bars)
    row0 = df.iloc[0]
    expected = tag_row(int(row0["bar_ts"]))
    for key, value in expected.items():
        assert row0[key] == value


def test_core_metrics_match_compute_on_the_same_trailing_window():
    # Direct regression check: the rolling loop's per-step values must
    # match the original compute() called on that exact trailing window.
    # Step 0's window is rets[0:MIN_OBSERVATIONS] -- MIN_OBSERVATIONS
    # returns built from MIN_OBSERVATIONS+1 close prices (pct_change drops
    # the first row), so the equivalent compute() call needs that same
    # +1-row window, not MIN_OBSERVATIONS bars.
    bars = _make_bars(n=MIN_OBSERVATIONS + 10)
    df = run_core_metrics_backtest("AAPL", "1D", bars)
    row0 = df.iloc[0]
    window_bars = bars.iloc[0 : MIN_OBSERVATIONS + 1]
    direct = compute("AAPL", bars=window_bars, time_format="1D").iloc[0]
    for field in ("sharpe_ratio", "sortino_ratio", "max_drawdown", "win_rate", "cagr"):
        assert row0[field] == direct[field]


def test_whole_history_metrics_is_one_untagged_row():
    bars = _make_bars(n=MIN_OBSERVATIONS + 10)
    df = run_whole_history_metrics("AAPL", "1D", bars)
    assert len(df) == 1
    assert "session" not in df.columns
    assert "bar_ts" not in df.columns
    for field in ("var_95", "var_99", "cvar_95", "tail_ratio", "skewness", "kurtosis"):
        assert field in df.columns


def test_whole_history_metrics_match_compute_on_full_series():
    bars = _make_bars(n=MIN_OBSERVATIONS + 10)
    df = run_whole_history_metrics("AAPL", "1D", bars)
    direct = compute("AAPL", bars=bars, time_format="1D").iloc[0]
    for field in ("var_95", "var_99", "cvar_95", "skewness", "kurtosis"):
        assert df.iloc[0][field] == direct[field]


def test_too_short_history_produces_no_core_rows():
    bars = _make_bars(n=MIN_OBSERVATIONS - 1)
    df = run_core_metrics_backtest("AAPL", "1D", bars)
    assert len(df) == 0
