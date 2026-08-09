from __future__ import annotations

import numpy as np
import pandas as pd

from vinu_initial_analysis.angles._tagging import tag_row
from vinu_initial_analysis.angles.drawdown_deep_dive.backtest import (
    K_SWEEP,
    run_drawdown_detection,
    run_k_sweep,
)
from vinu_initial_analysis.angles.drawdown_deep_dive.drawdown import (
    atr_pct_series,
    detect_drawdown_episodes,
)


def _make_bars(close: np.ndarray) -> pd.DataFrame:
    n = len(close)
    high = close * 1.001
    low = close * 0.999
    bar_ts = list(range(1_700_000_000, 1_700_000_000 + n * 86400, 86400))
    return pd.DataFrame({"bar_ts": bar_ts, "high": high, "low": low, "close": close})


def _recovered_scenario_bars(seed: int = 0) -> pd.DataFrame:
    """15 stable bars (ATR warmup), a sharp -10% drop, a few low bars, then
    a recovery back above the original peak."""
    rng = np.random.default_rng(seed)
    stable = 100 + rng.normal(0, 0.3, size=15)
    drop = [stable[-1] * 0.90]
    low_bars = [drop[0] * 0.995, drop[0] * 1.0, drop[0] * 0.99]
    recovery = [drop[0] * 1.03, drop[0] * 1.06, stable[-1] * 1.02, stable[-1] * 1.05]
    close = np.concatenate([stable, drop, low_bars, recovery])
    return _make_bars(close)


def test_atr_pct_series_has_no_lookahead_and_warms_up_at_period():
    bars = _recovered_scenario_bars()
    atr = atr_pct_series(bars, period=14)
    assert all(a is None for a in atr[:13])
    assert atr[13] is not None
    assert all(a is not None for a in atr[13:])


def test_detects_one_recovered_episode_with_full_lifecycle():
    bars = _recovered_scenario_bars()
    episodes = detect_drawdown_episodes("AAPL", bars, k=2.0)
    assert len(episodes) == 1
    ep = episodes[0]
    assert ep["status"] == "recovered"
    assert ep["drop_pct"] < -5  # a real, sharp drop, not noise
    # Compare against the *unrounded* relationship (rounding
    # threshold_pct_used from the raw atr_pct and rounding
    # atr_pct_at_peak for display are done independently, so re-deriving
    # from the already-rounded field can differ by ~1e-4).
    assert abs(ep["threshold_pct_used"] - (-max(2.0 * ep["atr_pct_at_peak"], 0.5))) < 1e-3
    assert ep["recovery_ts"] is not None
    assert ep["recovery_gain_pct"] > 0
    assert ep["duration_to_recovery"] is not None


def test_unrecovered_episode_marked_open_with_null_recovery_fields():
    rng = np.random.default_rng(1)
    stable = 100 + rng.normal(0, 0.3, size=15)
    drop = [stable[-1] * 0.90, stable[-1] * 0.88, stable[-1] * 0.85]  # never recovers
    close = np.concatenate([stable, drop])
    bars = _make_bars(close)
    episodes = detect_drawdown_episodes("AAPL", bars, k=2.0)
    assert len(episodes) == 1
    ep = episodes[0]
    assert ep["status"] == "open"
    assert ep["recovery_ts"] is None
    assert ep["recovery_price"] is None
    assert ep["recovery_checkpoints"] is None
    assert ep["recovery_news"] == []


def test_min_threshold_floor_applies_when_atr_is_tiny():
    # Perfectly flat prices -> ATR ~ 0 -> without the floor, k*atr would
    # let noise-level moves count as drawdowns.
    close = np.full(20, 100.0)
    close[19] = 99.99  # a 0.01% wiggle, must NOT trigger given the -0.5% floor
    bars = _make_bars(close)
    episodes = detect_drawdown_episodes("AAPL", bars, k=2.0, min_threshold_pct=-0.5)
    assert episodes == []


def test_formation_checkpoints_have_candle_and_price():
    bars = _recovered_scenario_bars()
    episodes = detect_drawdown_episodes("AAPL", bars, k=2.0)
    cp = episodes[0]["formation_checkpoints"]
    assert set(cp.keys()) == {"25%", "50%", "75%"}
    for v in cp.values():
        if v is not None:
            assert set(v.keys()) == {"candle", "price"}


def test_run_drawdown_detection_rows_are_tagged_by_peak_ts():
    bars = _recovered_scenario_bars()
    df = run_drawdown_detection("AAPL", "1D", bars, k=2.0)
    assert len(df) == 1
    row0 = df.iloc[0]
    expected = tag_row(int(row0["bar_ts"]))
    for key, value in expected.items():
        assert row0[key] == value
    assert row0["bar_ts"] == row0["peak_ts"]


def test_no_episodes_on_flat_data_returns_empty_dataframe_not_error():
    close = np.full(20, 100.0)
    bars = _make_bars(close)
    df = run_drawdown_detection("AAPL", "1D", bars, k=2.0)
    assert len(df) == 0
    assert isinstance(df, pd.DataFrame)


def test_k_sweep_runs_every_k_and_reports_n_episodes():
    bars = _recovered_scenario_bars()
    df = run_k_sweep("AAPL", "1D", bars)
    assert len(df) == len(K_SWEEP)
    assert list(df["k"]) == list(K_SWEEP)
    assert (df["n_episodes"] >= 0).all()
