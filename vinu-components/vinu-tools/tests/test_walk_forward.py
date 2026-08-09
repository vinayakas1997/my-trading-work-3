from __future__ import annotations

import os

import pandas as pd
import pytest

import pickle

from vinu_tools.compute.backtest.walk_forward import (
    StepResult,
    WalkForwardJob,
    _default_n_workers,
    run_walk_forward,
    run_walk_forward_parallel,
    run_walk_forward_parallel_batch,
)


def _bars(n: int) -> pd.DataFrame:
    return pd.DataFrame({"bar_ts": list(range(1000, 1000 + n)), "close": [float(i) for i in range(n)]})


def _module_level_step_fn(step):
    """Must be module-level (not a local closure) -- ProcessPoolExecutor
    pickles a reference to this function, not captured local state."""
    history = step.history["close"].astype(float).values
    return StepResult(row={
        "n_history": len(history),
        "last_close": float(history[-1]),
        "history_sum": float(history.sum()),
    })


def _module_level_tag_fn(bar_ts):
    """Same module-level constraint as step_fn -- a lambda here failed
    pickling to the worker process (confirmed while writing this test)."""
    return {"parity": bar_ts % 2}


def _step_fn_always_fails_on_step_index_3(step):
    if step.step_index == 3:
        raise RuntimeError("permanent simulated failure")
    return StepResult(row={"n_history": len(step.history)})


def _step_fn_fails_first_attempt_at_step_3(step):
    """Fails exactly once for step_index==3 (tracked via a file-based
    counter, since a retry may land on a different worker process where
    an in-memory counter wouldn't persist), then succeeds -- simulates a
    transient failure that retry should recover from. Requires
    WF_TEST_COUNTER_DIR to be set in the environment before the pool is
    created (spawned workers inherit the parent's environment)."""
    import os
    from pathlib import Path

    if step.step_index == 3:
        counter_file = Path(os.environ["WF_TEST_COUNTER_DIR"]) / "attempts.txt"
        attempts_so_far = int(counter_file.read_text()) if counter_file.is_file() else 0
        counter_file.write_text(str(attempts_so_far + 1))
        if attempts_so_far == 0:
            raise RuntimeError("simulated transient failure, first attempt only")
    return StepResult(row={"n_history": len(step.history)})


def _step_fn_always_raises(step):
    raise RuntimeError("this step_fn must never actually run if resume works")


def test_expanding_window_grows_each_step():
    lengths = []

    def step_fn(step):
        lengths.append(len(step.history))
        return StepResult(row={"forecast": 0.0})

    run_walk_forward("AAPL", "1D", _bars(20), step_fn, min_observations=15, horizon=2)
    assert lengths == [15, 16, 17, 18]


def test_rolling_window_stays_fixed_size():
    lengths = []

    def step_fn(step):
        lengths.append(len(step.history))
        return StepResult(row={})

    run_walk_forward("AAPL", "1H", _bars(10), step_fn, min_observations=4, window=3)
    assert lengths == [3, 3, 3, 3, 3, 3]


def test_tail_bars_without_full_horizon_are_never_decision_points():
    def step_fn(step):
        assert len(step.future) == 3
        return StepResult(row={})

    df = run_walk_forward("AAPL", "1D", _bars(20), step_fn, min_observations=15, horizon=3)
    assert df["bar_ts"].max() == 1000 + 20 - 1 - 3


def test_refit_cadence_flags_correct_steps():
    flags = []

    def step_fn(step):
        flags.append(step.is_refit_step)
        return StepResult(row={})

    run_walk_forward("AAPL", "1D", _bars(20), step_fn, min_observations=15, refit_cadence=3)
    assert flags == [True, False, False, True, False]


def test_prior_state_chains_across_steps():
    seen_prior = []

    def step_fn(step):
        seen_prior.append(step.prior_state)
        return StepResult(row={}, state=step.step_index)

    run_walk_forward("AAPL", "1D", _bars(20), step_fn, min_observations=17)
    assert seen_prior == [None, 0, 1]


def test_tag_fn_merged_into_every_row():
    def step_fn(step):
        return StepResult(row={"x": 1})

    df = run_walk_forward(
        "AAPL", "1D", _bars(17), step_fn, min_observations=15,
        tag_fn=lambda bar_ts: {"parity": bar_ts % 2},
    )
    assert "parity" in df.columns
    assert len(df) == 2


def test_weights_sink_called_only_when_weights_returned():
    sunk = []

    def step_fn(step):
        weights = {"w": step.step_index} if step.step_index % 2 == 0 else None
        return StepResult(row={}, weights=weights)

    def sink(symbol, timeframe, bar_ts, weights):
        sunk.append((symbol, timeframe, bar_ts, weights))
        return f"ref-{bar_ts}"

    df = run_walk_forward("AAPL", "1D", _bars(19), step_fn, min_observations=15, weights_sink=sink)
    assert len(sunk) == 2
    assert df["weights_ref"].isna().sum() == 2


def test_no_weights_sink_means_no_weights_ref_column():
    def step_fn(step):
        return StepResult(row={}, weights={"w": 1})

    df = run_walk_forward("AAPL", "1D", _bars(16), step_fn, min_observations=15)
    assert "weights_ref" not in df.columns


def test_min_observations_must_be_positive():
    with pytest.raises(ValueError):
        run_walk_forward("AAPL", "1D", _bars(10), lambda step: StepResult(row={}), min_observations=0)


def test_parallel_rejects_expanding_window():
    with pytest.raises(ValueError):
        run_walk_forward_parallel(
            "AAPL", "1D", _bars(20), _module_level_step_fn,
            min_observations=15, window="expanding",  # type: ignore[arg-type]
        )


def test_parallel_matches_sequential_row_for_row():
    bars = _bars(97)  # deliberately not a multiple of chunk_size
    sequential = run_walk_forward(
        "AAPL", "1D", bars, _module_level_step_fn,
        min_observations=15, window=15, horizon=3,
        tag_fn=_module_level_tag_fn,
    )
    parallel = run_walk_forward_parallel(
        "AAPL", "1D", bars, _module_level_step_fn,
        min_observations=15, window=15, horizon=3,
        tag_fn=_module_level_tag_fn,
        chunk_size=10, n_workers=3,
    )
    pd.testing.assert_frame_equal(
        sequential.reset_index(drop=True), parallel.reset_index(drop=True)
    )


def test_parallel_chunk_boundaries_drop_or_duplicate_nothing():
    bars = _bars(50)
    parallel = run_walk_forward_parallel(
        "AAPL", "1D", bars, _module_level_step_fn,
        min_observations=10, window=10, horizon=1,
        chunk_size=7,  # deliberately does not divide the step count evenly
    )
    assert parallel["step_index"].tolist() == list(range(len(parallel)))
    assert parallel["bar_ts"].is_unique


def test_parallel_empty_when_no_steps_fit():
    df = run_walk_forward_parallel(
        "AAPL", "1D", _bars(10), _module_level_step_fn,
        min_observations=15, window=15,
    )
    assert df.empty


def test_batch_matches_sequential_for_each_job_row_for_row():
    jobs = [
        WalkForwardJob(
            key="AAPL", symbol="AAPL", timeframe="1D", bars=_bars(97),
            step_fn=_module_level_step_fn, min_observations=15, window=15,
            horizon=3, tag_fn=_module_level_tag_fn, chunk_size=10,
        ),
        WalkForwardJob(
            key="TSLA", symbol="TSLA", timeframe="1D", bars=_bars(60),
            step_fn=_module_level_step_fn, min_observations=10, window=10,
            horizon=2, tag_fn=_module_level_tag_fn, chunk_size=8,
        ),
    ]
    # min_total_steps_for_parallel=0 forces the process-pool path even
    # though this batch is well under the real default threshold --
    # otherwise this test would silently exercise the sequential
    # fallback instead of the thing it's meant to test.
    result = run_walk_forward_parallel_batch(
        jobs, n_workers=3, min_total_steps_for_parallel=0
    )
    assert result.ok
    assert set(result.data.keys()) == {"AAPL", "TSLA"}

    for job in jobs:
        sequential = run_walk_forward(
            job.symbol, job.timeframe, job.bars, job.step_fn,
            min_observations=job.min_observations, window=job.window,
            horizon=job.horizon, tag_fn=job.tag_fn,
        )
        got = result.data[job.key].sort_values("step_index").reset_index(drop=True)
        pd.testing.assert_frame_equal(sequential.reset_index(drop=True), got)


def test_batch_rejects_expanding_window_job():
    jobs = [
        WalkForwardJob(
            key="AAPL", symbol="AAPL", timeframe="1D", bars=_bars(20),
            step_fn=_module_level_step_fn, min_observations=15, window="expanding",  # type: ignore[arg-type]
        ),
    ]
    with pytest.raises(ValueError):
        run_walk_forward_parallel_batch(jobs)


def test_batch_handles_a_job_with_no_valid_steps():
    jobs = [
        WalkForwardJob(
            key="TOO_SHORT", symbol="X", timeframe="1D", bars=_bars(5),
            step_fn=_module_level_step_fn, min_observations=15, window=15,
        ),
        WalkForwardJob(
            key="NORMAL", symbol="Y", timeframe="1D", bars=_bars(20),
            step_fn=_module_level_step_fn, min_observations=15, window=15,
        ),
    ]
    result = run_walk_forward_parallel_batch(jobs)
    assert result.ok
    assert result.data["TOO_SHORT"].empty
    assert not result.data["NORMAL"].empty


def test_default_n_workers_leaves_one_core_free():
    assert _default_n_workers(None) == max(1, (os.cpu_count() or 1) - 1)


def test_default_n_workers_never_goes_below_one(monkeypatch):
    monkeypatch.setattr(os, "cpu_count", lambda: 1)
    assert _default_n_workers(None) == 1


def test_default_n_workers_explicit_value_always_wins():
    assert _default_n_workers(7) == 7


def test_batch_falls_back_to_sequential_when_too_small(monkeypatch):
    # A single-job (or small-total-steps) batch should never spin up a
    # process pool at all -- measured directly this session that doing
    # so is a net loss below a real amount of work. Confirmed here by
    # making ProcessPoolExecutor itself explode if it's ever constructed.
    def _boom(*args, **kwargs):
        raise AssertionError("ProcessPoolExecutor should not be created for a too-small batch")

    monkeypatch.setattr("concurrent.futures.ProcessPoolExecutor", _boom)

    jobs = [
        WalkForwardJob(
            key="AAPL", symbol="AAPL", timeframe="1D", bars=_bars(30),
            step_fn=_module_level_step_fn, min_observations=15, window=15,
        ),
    ]
    result = run_walk_forward_parallel_batch(jobs)  # default threshold, single job
    assert result.ok
    assert not result.data["AAPL"].empty


def test_batch_sequential_fallback_matches_forced_parallel_path():
    jobs = [
        WalkForwardJob(
            key="AAPL", symbol="AAPL", timeframe="1D", bars=_bars(97),
            step_fn=_module_level_step_fn, min_observations=15, window=15,
            horizon=3, tag_fn=_module_level_tag_fn, chunk_size=10,
        ),
        WalkForwardJob(
            key="TSLA", symbol="TSLA", timeframe="1D", bars=_bars(60),
            step_fn=_module_level_step_fn, min_observations=10, window=10,
            horizon=2, tag_fn=_module_level_tag_fn, chunk_size=8,
        ),
    ]
    # default threshold (1500) -- this small batch takes the sequential
    # fallback path, not the process pool.
    fallback = run_walk_forward_parallel_batch(jobs)
    forced_parallel = run_walk_forward_parallel_batch(
        jobs, n_workers=3, min_total_steps_for_parallel=0
    )
    assert fallback.ok and forced_parallel.ok
    for key in ("AAPL", "TSLA"):
        pd.testing.assert_frame_equal(
            fallback.data[key].reset_index(drop=True),
            forced_parallel.data[key].sort_values("step_index").reset_index(drop=True),
        )


def test_batch_retries_a_transiently_failing_chunk_and_recovers(tmp_path, monkeypatch):
    monkeypatch.setenv("WF_TEST_COUNTER_DIR", str(tmp_path))
    jobs = [
        WalkForwardJob(
            key="AAPL", symbol="AAPL", timeframe="1D", bars=_bars(40),
            step_fn=_step_fn_fails_first_attempt_at_step_3,
            min_observations=15, window=15, chunk_size=5,
        ),
    ]
    result = run_walk_forward_parallel_batch(jobs, min_total_steps_for_parallel=0, max_retries=2)
    assert result.ok, f"expected the transient failure to be recovered by retry, got failures: {result.failures}"
    assert len(result.data["AAPL"]) == 25  # nothing lost -- every step present


def test_batch_records_permanent_failure_without_losing_other_jobs():
    jobs = [
        WalkForwardJob(
            key="BAD", symbol="BAD", timeframe="1D", bars=_bars(40),
            step_fn=_step_fn_always_fails_on_step_index_3,
            min_observations=15, window=15, chunk_size=5,
        ),
        WalkForwardJob(
            key="GOOD", symbol="GOOD", timeframe="1D", bars=_bars(40),
            step_fn=_module_level_step_fn,
            min_observations=15, window=15, chunk_size=5,
        ),
    ]
    result = run_walk_forward_parallel_batch(jobs, min_total_steps_for_parallel=0, max_retries=1)

    assert not result.ok
    assert len(result.failures) == 1
    assert result.failures[0].key == "BAD"
    assert result.failures[0].attempts == 2  # 1 initial attempt + 1 retry

    # GOOD job is completely unaffected by BAD job's chunk failing.
    assert len(result.data["GOOD"]) == 25
    # BAD job's OTHER 4 chunks (20 of 25 steps) still succeeded despite one chunk failing.
    assert len(result.data["BAD"]) == 20


def test_batch_resume_skips_recomputation_via_checkpoint(tmp_path):
    checkpoint_dir = tmp_path / "checkpoints"
    bars = _bars(40)

    first_job = WalkForwardJob(
        key="AAPL", symbol="AAPL", timeframe="1D", bars=bars,
        step_fn=_module_level_step_fn, min_observations=15, window=15, chunk_size=5,
    )
    first = run_walk_forward_parallel_batch(
        [first_job], min_total_steps_for_parallel=0, checkpoint_dir=checkpoint_dir,
    )
    assert first.ok
    checkpoint_files = list(checkpoint_dir.glob("*.pkl"))
    assert len(checkpoint_files) == 5  # one file per chunk (25 steps / chunk_size 5)

    # Same chunk boundaries (same bars/min_observations/window/chunk_size),
    # but a step_fn that ALWAYS raises -- if resume is actually skipping
    # recomputation (not just returning the right answer some other way),
    # this must still succeed, because the broken step_fn never runs.
    second_job = WalkForwardJob(
        key="AAPL", symbol="AAPL", timeframe="1D", bars=bars,
        step_fn=_step_fn_always_raises, min_observations=15, window=15, chunk_size=5,
    )
    second = run_walk_forward_parallel_batch(
        [second_job], min_total_steps_for_parallel=0,
        checkpoint_dir=checkpoint_dir, resume=True,
    )
    assert second.ok
    pd.testing.assert_frame_equal(
        first.data["AAPL"].reset_index(drop=True), second.data["AAPL"].reset_index(drop=True)
    )


def test_batch_resume_true_trusts_and_resume_false_discards_stale_checkpoint(tmp_path):
    checkpoint_dir = tmp_path / "checkpoints"
    bars = _bars(40)
    job = WalkForwardJob(
        key="AAPL", symbol="AAPL", timeframe="1D", bars=bars,
        step_fn=_module_level_step_fn, min_observations=15, window=15, chunk_size=5,
    )
    first = run_walk_forward_parallel_batch([job], min_total_steps_for_parallel=0, checkpoint_dir=checkpoint_dir)
    assert first.ok

    # overwrite one checkpoint file with valid-but-deliberately-wrong data
    stale_file = sorted(checkpoint_dir.glob("*.pkl"))[0]
    fake_rows = [{
        "symbol": "FAKE_STALE_VALUE", "timeframe": "1D", "bar_ts": 0, "step_index": -999,
        "n_history": -1,
    }]
    with open(stale_file, "wb") as f:
        pickle.dump(fake_rows, f)

    # resume=True (default) trusts whatever's checkpointed, even if stale
    resumed_true = run_walk_forward_parallel_batch(
        [job], min_total_steps_for_parallel=0, checkpoint_dir=checkpoint_dir, resume=True,
    )
    assert resumed_true.ok
    assert (resumed_true.data["AAPL"]["symbol"] == "FAKE_STALE_VALUE").any()

    # resume=False ignores/clears existing checkpoints and recomputes fresh
    resumed_false = run_walk_forward_parallel_batch(
        [job], min_total_steps_for_parallel=0, checkpoint_dir=checkpoint_dir, resume=False,
    )
    assert resumed_false.ok
    assert not (resumed_false.data["AAPL"]["symbol"] == "FAKE_STALE_VALUE").any()
    pd.testing.assert_frame_equal(
        first.data["AAPL"].reset_index(drop=True), resumed_false.data["AAPL"].reset_index(drop=True)
    )


def test_batch_corrupt_checkpoint_file_is_treated_as_missing_not_trusted():
    from vinu_tools.compute.backtest.walk_forward import _load_checkpoint

    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        corrupt = Path(d) / "corrupt.pkl"
        corrupt.write_bytes(b"not a real pickle stream at all")
        assert _load_checkpoint(corrupt) is None

        missing = Path(d) / "does_not_exist.pkl"
        assert _load_checkpoint(missing) is None
