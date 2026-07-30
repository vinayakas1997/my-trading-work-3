from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from vinu_portfolio.regime import classify_current_regime


def _returns(values) -> pd.Series:
    return pd.Series(values, index=pd.date_range("2024-01-01", periods=len(values)))


class TestClassifyCurrentRegime:
    def test_no_data_returns_status(self) -> None:
        result = classify_current_regime(pd.Series([], dtype=float))
        assert result["status"] == "no_data"
        assert result["regime"] is None

    def test_insufficient_data_below_window(self) -> None:
        result = classify_current_regime(_returns([0.001] * 10))
        assert result["status"] == "insufficient_data"
        assert result["regime"] is None
        assert result["n_observations"] == 10

    @staticmethod
    def _periodic_base() -> list[float]:
        # rolling(21).std() depends only on the *set* of values in each
        # window, not their order. A period-3 cycle repeated 13x (length 39,
        # and 21 is divisible by 3) gives every 21-day window the exact same
        # multiset of values -> identical, deterministic rolling vol with no
        # dependence on a random seed. Appending one more value at the end
        # (in the tests below) perturbs only the final window slightly.
        return [0.025, -0.025, 0.001] * 13

    def test_bull_when_recent_return_strongly_positive_and_vol_calm(self) -> None:
        calm = self._periodic_base() + [0.015]  # just above the 0.01 bull threshold
        result = classify_current_regime(_returns(calm))
        assert result["status"] == "ok"
        assert result["regime"] == "bull"

    def test_bear_when_recent_return_strongly_negative_and_vol_calm(self) -> None:
        calm = self._periodic_base() + [-0.015]
        result = classify_current_regime(_returns(calm))
        assert result["status"] == "ok"
        assert result["regime"] == "bear"

    def test_sideways_when_recent_return_small_and_vol_calm(self) -> None:
        calm = self._periodic_base() + [0.003]
        result = classify_current_regime(_returns(calm))
        assert result["status"] == "ok"
        assert result["regime"] == "sideways"

    def test_high_vol_overrides_return_sign(self) -> None:
        rng = np.random.default_rng(3)
        # Most days calm, but a spike right before the observation window
        # ends pushes trailing 21-day rolling vol for the latest day above
        # the series' own 0.7 quantile threshold.
        values = rng.normal(0.0, 0.0005, size=40).tolist()
        values[-21:-1] = [0.05, -0.05] * 10
        values[-1] = 0.02
        result = classify_current_regime(_returns(values))
        assert result["status"] == "ok"
        assert result["regime"] == "high_vol"
