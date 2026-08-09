from __future__ import annotations

import numpy as np
import pandas as pd

from vinu_initial_analysis.angles import _tagging
from vinu_initial_analysis.angles.arima import backtest as arima_backtest
from vinu_initial_analysis.angles.arima import compute as arima_compute
from vinu_initial_analysis.angles.arima.backtest import MIN_OBSERVATIONS, run_arima_backtest
from vinu_initial_analysis.angles.arima.naive_baseline import run_naive_baseline


def _make_bars(n: int, seed: int = 1) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(0, 0.5, size=n))
    bar_ts = list(range(1_700_000_000, 1_700_000_000 + n * 86400, 86400))
    return pd.DataFrame({"bar_ts": bar_ts, "close": close})


def test_produces_one_row_per_step_past_min_observations():
    bars = _make_bars(n=MIN_OBSERVATIONS + 15)
    df = run_arima_backtest("AAPL", "1D", bars, data_root="unused")
    assert len(df) == 15


def test_rows_are_tagged_consistently_with_tag_row():
    bars = _make_bars(n=MIN_OBSERVATIONS + 5)
    df = run_arima_backtest("AAPL", "1D", bars, data_root="unused")
    row0 = df.iloc[0]
    expected = _tagging.tag_row(int(row0["bar_ts"]))
    for key, value in expected.items():
        assert row0[key] == value


def test_hit_is_ci_coverage_not_direction_match():
    bars = _make_bars(n=MIN_OBSERVATIONS + 10)
    df = run_arima_backtest("AAPL", "1D", bars, data_root="unused")
    ok = df[df["status"] == "ok"]
    assert len(ok) > 0
    for _, row in ok.iterrows():
        lower, upper = row["confidence_interval"]
        expected_hit = int(lower <= row["actual_price"] <= upper)
        assert row["hit"] == expected_hit


def test_no_weights_ref_column_arima_does_not_train_a_model():
    bars = _make_bars(n=MIN_OBSERVATIONS + 5)
    df = run_arima_backtest("AAPL", "1D", bars, data_root="unused")
    assert "weights_ref" not in df.columns


def test_daily_timeframe_refits_every_step(monkeypatch):
    calls = {"n": 0}
    real_fit = arima_compute._fit_best_arima

    def counting_fit(close):
        calls["n"] += 1
        return real_fit(close)

    monkeypatch.setattr(arima_compute, "_fit_best_arima", counting_fit)
    bars = _make_bars(n=MIN_OBSERVATIONS + 6)
    df = run_arima_backtest("AAPL", "1D", bars, data_root="unused")
    assert calls["n"] == len(df)  # REFIT_CADENCE["1D"] == 1: every step refits


def test_1min_timeframe_reuses_prior_state_between_refits(monkeypatch):
    calls = {"n": 0}
    real_fit = arima_compute._fit_best_arima

    def counting_fit(close):
        calls["n"] += 1
        return real_fit(close)

    monkeypatch.setattr(arima_compute, "_fit_best_arima", counting_fit)
    cadence = arima_backtest.REFIT_CADENCE["1min"]
    n_steps = cadence * 3 + 1  # spans multiple refit cycles
    bars = _make_bars(n=MIN_OBSERVATIONS + n_steps)
    df = run_arima_backtest("AAPL", "1min", bars, data_root="unused")
    expected_refits = sum(1 for i in range(len(df)) if i % cadence == 0)
    assert calls["n"] == expected_refits
    assert calls["n"] < len(df)  # confirms the cadence is actually saving real fits


def test_parallel_output_is_row_for_row_identical_to_sequential_at_cadence_1():
    # 1D has REFIT_CADENCE == 1 (refits every step sequentially too), so
    # the parallel path's "every step is a fresh independent fit" behavior
    # matches sequential exactly here -- a pure scheduling change.
    bars = _make_bars(n=MIN_OBSERVATIONS + 20)
    sequential = run_arima_backtest("AAPL", "1D", bars, data_root="unused")
    parallel = run_arima_backtest(
        "AAPL", "1D", bars, data_root="unused", parallel=True, chunk_size=5, n_workers=2,
    )
    pd.testing.assert_frame_equal(
        sequential.reset_index(drop=True), parallel.reset_index(drop=True),
    )


def test_parallel_at_cadence_greater_than_1_runs_but_is_not_identical_to_sequential():
    # 1min has REFIT_CADENCE > 1: sequential mode only fully refits every
    # Nth step and cheaply extends the fit in between; the parallel path
    # has no refit_cadence/prior_state support at all and fully refits
    # every step -- a real, documented behavior difference, not a bug.
    # This proves it runs successfully (no crash) and that it genuinely
    # differs from sequential, rather than silently claiming identical
    # output it can't actually produce for this cadence.
    cadence = arima_backtest.REFIT_CADENCE["1min"]
    n_steps = cadence * 2 + 3
    bars = _make_bars(n=MIN_OBSERVATIONS + n_steps)
    sequential = run_arima_backtest("AAPL", "1min", bars, data_root="unused")
    parallel = run_arima_backtest(
        "AAPL", "1min", bars, data_root="unused", parallel=True, chunk_size=5, n_workers=2,
    )
    assert len(sequential) == len(parallel) > 0
    # At least one step differs (a fresh AIC-search refit vs an extended
    # fit is not guaranteed to land on the exact same forecast/order).
    # Only compare rows where both sides actually fit successfully.
    ok_rows = [
        i for i in range(len(sequential))
        if sequential.iloc[i]["status"] == "ok" and parallel.iloc[i]["status"] == "ok"
    ]
    assert ok_rows
    orders_differ_or_forecasts_differ = any(
        sequential.iloc[i]["forecast"] != parallel.iloc[i]["forecast"]
        or tuple(sequential.iloc[i]["order"].values()) != tuple(parallel.iloc[i]["order"].values())
        for i in ok_rows
    )
    assert orders_differ_or_forecasts_differ


def test_naive_baseline_forecast_is_always_last_close():
    bars = _make_bars(n=MIN_OBSERVATIONS + 8)
    df = run_naive_baseline("AAPL", "1D", bars)
    assert len(df) == 8
    for i, row in df.iterrows():
        history_len = MIN_OBSERVATIONS + i
        assert row["forecast"] == bars["close"].iloc[history_len - 1]
        assert row["squared_error"] == (row["actual_price"] - row["forecast"]) ** 2


def test_naive_baseline_has_no_hit_or_weights_columns():
    bars = _make_bars(n=MIN_OBSERVATIONS + 3)
    df = run_naive_baseline("AAPL", "1D", bars)
    assert "hit" not in df.columns
    assert "weights_ref" not in df.columns
