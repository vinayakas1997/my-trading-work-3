from __future__ import annotations

import pandas as pd
import pytest

from vinu_portfolio.regime import (
    _ROLLING_WINDOW,
    _VOL_BASELINE_WINDOW,
    classify_current_regime,
)


def _returns(values) -> pd.Series:
    return pd.Series(values, index=pd.date_range("2024-01-01", periods=len(values)))


def _periodic_base(n_cycles: int = 50) -> list[float]:
    # rolling(21).std() depends only on the *set* of values in each window,
    # not their order. A period-3 cycle (21 is divisible by 3) gives every
    # interior 21-day window the exact same multiset of values -> a flat,
    # deterministic vol plateau, so the 120-day trailing baseline mean/std
    # of that plateau is stable and a tail perturbation is easy to reason
    # about without relying on random-seed luck.
    return [0.025, -0.025, 0.001] * n_cycles


class TestClassifyCurrentRegime:
    def test_no_data_returns_status(self) -> None:
        result = classify_current_regime(pd.Series([], dtype=float))
        assert result["status"] == "no_data"
        assert result["regime"] is None

    def test_insufficient_data_below_min_observations(self) -> None:
        min_observations = _ROLLING_WINDOW + _VOL_BASELINE_WINDOW
        result = classify_current_regime(_returns([0.001] * (min_observations - 1)))
        assert result["status"] == "insufficient_data"
        assert result["regime"] is None
        assert result["n_observations"] == min_observations - 1

    def test_bull_when_recent_return_strongly_positive_and_vol_calm(self) -> None:
        calm = _periodic_base() + [0.015]  # just above the 0.01 bull threshold
        result = classify_current_regime(_returns(calm))
        assert result["status"] == "ok"
        assert result["regime"] == "bull"

    def test_bear_when_recent_return_strongly_negative_and_vol_calm(self) -> None:
        calm = _periodic_base() + [-0.015]
        result = classify_current_regime(_returns(calm))
        assert result["status"] == "ok"
        assert result["regime"] == "bear"

    def test_sideways_when_recent_return_small_and_vol_calm(self) -> None:
        calm = _periodic_base() + [0.003]
        result = classify_current_regime(_returns(calm))
        assert result["status"] == "ok"
        assert result["regime"] == "sideways"

    def test_high_vol_overrides_return_sign(self) -> None:
        # A real spike in the trailing 21-day window relative to the 120-day
        # baseline plateau established by the periodic base.
        base = _periodic_base()
        spike = base[:-20] + [0.08, -0.08] * 10 + [0.02]
        result = classify_current_regime(_returns(spike))
        assert result["status"] == "ok"
        assert result["regime"] == "high_vol"

