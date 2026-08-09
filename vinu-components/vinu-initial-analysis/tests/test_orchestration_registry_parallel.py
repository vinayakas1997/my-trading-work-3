from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import pandas as pd
import pytest

from vinu_initial_analysis.storage.orchestration import AngleRunStatus, run_batch
from vinu_initial_analysis.storage.orchestration_registry import (
    PARALLEL_SAFE_ANGLES,
    build_batch_jobs,
    build_walk_forward_jobs,
    run_batch_with_parallel_harness,
)

# Only the 4 cheap classical-stats parallel-safe angles -- chronos/kronos/
# timer_timerxl need a real pretrained model load per worker, too expensive
# for a permanent unit test (see test_{chronos,kronos}_backtest.py's own
# "only run the real model once" precedent). Real proof for those 3 (and
# for this whole integration, end to end) was done via a real ad-hoc script
# against real AAPL/JNJ/TSLA data -- see
# New-talk-/07-orchestration-suite-test/05-parallel-harness-integration.md.
_CHEAP_PARALLEL_ANGLES = ["arima", "exponential_smoothing", "garch", "kalman_filters"]


def _make_bars(n: int, seed: int = 1) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(0, 0.5, size=n))
    bar_ts = list(range(1_700_000_000, 1_700_000_000 + n * 86400, 86400))
    return pd.DataFrame({"bar_ts": bar_ts, "close": close})


def _make_ohlc_bars(n: int, seed: int = 1) -> pd.DataFrame:
    df = _make_bars(n, seed)
    rng = np.random.default_rng(seed + 100)
    close = df["close"].to_numpy()
    open_p = close + rng.normal(0, 0.2, size=n)
    high = np.maximum(close, open_p) + np.abs(rng.normal(0, 0.3, size=n))
    low = np.minimum(close, open_p) - np.abs(rng.normal(0, 0.3, size=n))
    df["open"] = open_p
    df["high"] = high
    df["low"] = low
    return df


def test_build_walk_forward_jobs_only_includes_parallel_safe_angles():
    bars_by_symbol = {"AAPL": _make_bars(120)}
    jobs = build_walk_forward_jobs(
        ["AAPL"], bars_by_symbol,
        angle_names=["arima", "shock_clustering", "kalman_filters", "pnl_attribution"],
    )
    # shock_clustering/pnl_attribution aren't parallel-safe -- silently
    # excluded, not an error (callers that want a mixed batch use
    # run_batch_with_parallel_harness, which does the split explicitly).
    keys = {j.key for j in jobs}
    assert keys == {"AAPL:arima", "AAPL:kalman_filters"}


def test_build_walk_forward_jobs_uses_each_angles_real_config():
    bars_by_symbol = {"AAPL": _make_bars(120)}
    jobs = build_walk_forward_jobs(["AAPL"], bars_by_symbol, angle_names=["arima"])
    assert len(jobs) == 1
    job = jobs[0]
    assert job.min_observations == 100  # arima's real MIN_OBSERVATIONS
    assert job.window == 100
    assert job.horizon == 1
    assert callable(job.step_fn)


def test_build_walk_forward_jobs_garch_step_fn_is_picklable_with_timeframe_bound():
    # garch's real step_fn needs `timeframe` bound (volatility annualization
    # depends on it) -- must be a functools.partial over the module-level
    # _garch_step, not a closure, or it won't survive being pickled to a
    # worker process. Confirmed directly rather than assumed.
    import pickle

    bars_by_symbol = {"AAPL": _make_bars(120)}
    jobs = build_walk_forward_jobs(["AAPL"], bars_by_symbol, angle_names=["garch"], timeframe="1H")
    assert len(jobs) == 1
    pickle.loads(pickle.dumps(jobs[0].step_fn))  # must not raise


@pytest.mark.parametrize("angle_name", _CHEAP_PARALLEL_ANGLES)
def test_parallel_harness_output_matches_sequential_for_each_cheap_angle(angle_name):
    bars_by_symbol = {"AAPL": _make_bars(130), "TSLA": _make_bars(130, seed=2)}
    symbols = list(bars_by_symbol)
    with TemporaryDirectory() as tmp:
        seq_tracker = AngleRunStatus(Path(tmp) / "seq.db")
        par_tracker = AngleRunStatus(Path(tmp) / "par.db")
        try:
            seq_jobs = build_batch_jobs(symbols, bars_by_symbol, tmp, angle_names=[angle_name])
            seq_summary = run_batch(seq_tracker, "seq", seq_jobs, max_attempts=1)

            par_summary = run_batch_with_parallel_harness(
                par_tracker, "par", symbols, bars_by_symbol, tmp,
                angle_names=[angle_name], n_workers=2, chunk_size=20,
                min_total_steps_for_parallel=0,  # force the real process-pool path
            )

            assert seq_summary["ok"] and par_summary["ok"]
            for symbol in symbols:
                key = f"{symbol}:{angle_name}"
                pd.testing.assert_frame_equal(
                    seq_summary["results"][key].reset_index(drop=True),
                    par_summary["results"][key].reset_index(drop=True),
                )
        finally:
            seq_tracker.close()
            par_tracker.close()


def test_parallel_harness_mixed_batch_parallel_and_sequential_angles_both_complete():
    # A real mixed batch: arima/kalman_filters (parallel-safe, shared pool)
    # + shock_clustering (not parallel-safe, sequential fallback loop) in
    # ONE call -- proves the split-and-merge actually works, not just each
    # half in isolation.
    bars_by_symbol = {"AAPL": _make_ohlc_bars(130)}
    symbols = ["AAPL"]
    angle_names = ["arima", "kalman_filters", "shock_clustering"]
    with TemporaryDirectory() as tmp:
        tracker = AngleRunStatus(Path(tmp) / "mixed.db")
        try:
            summary = run_batch_with_parallel_harness(
                tracker, "mixed", symbols, bars_by_symbol, tmp,
                angle_names=angle_names, n_workers=2, chunk_size=20,
                min_total_steps_for_parallel=0,
            )
            assert summary["ok"]
            assert set(summary["results"]) == {
                "AAPL:arima", "AAPL:kalman_filters", "AAPL:shock_clustering",
            }
            # Full visibility + self-cleanup: every job registered, batch's
            # rows gone once everything succeeded -- same real contract as
            # plain run_batch().
            assert tracker.get_batch_status("mixed") == []
        finally:
            tracker.close()


def test_parallel_harness_marks_a_failed_parallel_job_without_losing_the_others(monkeypatch):
    # Real fault-isolation check on the integration logic itself: every
    # one of the 4 cheap angles' step_fns already catches its own
    # insufficient-data/fit errors internally (returns a "fit_failed"
    # status row, never raises) -- by design, so there's no real
    # data-driven way to make a chunk genuinely raise here. What's
    # actually worth proving at this layer is that a ChunkFailure coming
    # back from run_walk_forward_parallel_batch gets correctly translated
    # into tracker.mark_failed()/errors[key] for the failed job while the
    # other job's real result and tracker row are untouched -- proven by
    # substituting a canned BatchResult with one deliberate failure,
    # rather than by trying to force a real crash through real data.
    import vinu_initial_analysis.storage.orchestration_registry as registry_module
    from vinu_tools.compute.backtest.walk_forward import BatchResult, ChunkFailure

    real_df = pd.DataFrame([{"status": "ok"}])

    def fake_run_walk_forward_parallel_batch(jobs, **kwargs):
        return BatchResult(
            data={"TSLA:arima": real_df},
            failures=[ChunkFailure(key="AAPL:arima", start_position=0, end_position=10, attempts=3, error="boom")],
        )

    monkeypatch.setattr(
        registry_module, "run_walk_forward_parallel_batch", fake_run_walk_forward_parallel_batch,
    )

    bars_by_symbol = {"AAPL": _make_bars(130), "TSLA": _make_bars(130, seed=4)}
    symbols = list(bars_by_symbol)
    with TemporaryDirectory() as tmp:
        tracker = AngleRunStatus(Path(tmp) / "fail.db")
        try:
            summary = run_batch_with_parallel_harness(
                tracker, "fail", symbols, bars_by_symbol, tmp,
                angle_names=["arima"], n_workers=2, chunk_size=20,
                min_total_steps_for_parallel=0,
            )
            assert not summary["ok"]
            assert summary["results"]["TSLA:arima"] is real_df
            assert "AAPL:arima" in summary["errors"]
            assert "boom" in summary["errors"]["AAPL:arima"]
            # The batch as a whole isn't complete (AAPL failed), so rows are
            # NOT deleted -- both symbols' rows stay visible: AAPL shows the
            # real failure, TSLA shows it succeeded, neither lost nor hidden.
            remaining = {row["symbol"]: row["status"] for row in tracker.get_batch_status("fail")}
            assert remaining == {"AAPL": "failed", "TSLA": "ok"}
        finally:
            tracker.close()
