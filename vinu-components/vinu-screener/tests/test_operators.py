from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from vinu_screener.features import operators as op


def _s(vals) -> pd.Series:
    return pd.Series(vals, dtype=float)


class TestSimpleOperators:
    def test_ref_shifts_by_offset(self) -> None:
        s = _s([1, 2, 3, 4, 5])
        out = op.ref(s, 2)
        assert out.iloc[-1] == 3

    def test_delta(self) -> None:
        s = _s([10, 12, 15, 20])
        out = op.delta(s, 1)
        assert out.iloc[-1] == 5  # 20 - 15

    def test_pct_change(self) -> None:
        s = _s([100, 110])
        out = op.pct_change(s)
        assert out.iloc[-1] == pytest.approx(0.10)


class TestMovingAverages:
    def test_sma_matches_hand_computation(self) -> None:
        s = _s([1, 2, 3, 4, 5])
        out = op.sma(s, 3)
        assert out.iloc[-1] == pytest.approx((3 + 4 + 5) / 3)
        assert pd.isna(out.iloc[0])

    def test_ema_converges_toward_a_constant_series(self) -> None:
        s = _s([10.0] * 30)
        out = op.ema(s, 5)
        assert out.iloc[-1] == pytest.approx(10.0)

    def test_wma_weights_recent_bars_more(self) -> None:
        s = _s([1, 1, 1, 100])  # last bar dominates
        out = op.wma(s, 4)
        assert out.iloc[-1] > op.sma(s, 4).iloc[-1]


class TestStdRankSlope:
    def test_rolling_std_of_constant_series_is_zero(self) -> None:
        s = _s([5.0] * 10)
        out = op.rolling_std(s, 5)
        assert out.iloc[-1] == pytest.approx(0.0)

    def test_rolling_rank_of_the_max_value_is_one(self) -> None:
        s = _s([1, 3, 2, 4, 5])  # current (last) value 5 is the max of its own window
        out = op.rolling_rank(s, 5)
        assert out.iloc[-1] == pytest.approx(1.0)

    def test_slope_of_a_straight_line_matches_its_step(self) -> None:
        s = _s(np.arange(20) * 2.0)  # slope 2 per bar
        out = op.slope(s, 10)
        assert out.iloc[-1] == pytest.approx(2.0, abs=1e-9)

    def test_slope_of_a_flat_series_is_zero(self) -> None:
        s = _s([7.0] * 15)
        out = op.slope(s, 10)
        assert out.iloc[-1] == pytest.approx(0.0)


class TestRSI:
    def test_all_gains_is_100(self) -> None:
        s = _s(np.arange(1, 30, dtype=float))  # monotonically rising
        out = op.rsi(s, 14)
        assert out.iloc[-1] == pytest.approx(100.0)

    def test_all_losses_is_0(self) -> None:
        s = _s(np.arange(30, 1, -1, dtype=float))  # monotonically falling
        out = op.rsi(s, 14)
        assert out.iloc[-1] == pytest.approx(0.0)

    def test_flat_series_is_neutral_or_nan_not_a_crash(self) -> None:
        s = _s([10.0] * 20)
        out = op.rsi(s, 14)
        assert not np.isinf(out.iloc[-1])


class TestMACD:
    def test_returns_three_named_columns(self) -> None:
        rng = np.random.default_rng(0)
        s = pd.Series(100 + np.cumsum(rng.normal(0, 1, 60)))
        out = op.macd(s)
        assert list(out.columns) == ["macd", "signal", "hist"]
        assert (out["hist"] == out["macd"] - out["signal"]).all() or out["hist"].isna().any()

    def test_hist_is_macd_minus_signal(self) -> None:
        rng = np.random.default_rng(1)
        s = pd.Series(100 + np.cumsum(rng.normal(0, 1, 60)))
        out = op.macd(s)
        diff = (out["hist"] - (out["macd"] - out["signal"])).dropna()
        assert (diff.abs() < 1e-9).all()
