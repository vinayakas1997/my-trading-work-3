from __future__ import annotations

import pandas as pd
import pytest

from vinu_tools.compute.backtest.walk_forward import StepResult, run_walk_forward


def _bars(n: int) -> pd.DataFrame:
    return pd.DataFrame({"bar_ts": list(range(1000, 1000 + n)), "close": [float(i) for i in range(n)]})


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
