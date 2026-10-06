"""The metrics angle's Sharpe must be the standard one (annualised arithmetic
mean over annualised volatility), the same as the simulator's. It was
CAGR / volatility, which inflated short windows: +35% in 72 days read 5.3
against 3.2."""
from __future__ import annotations

import numpy as np
import pytest

from vinu_initial_analysis.angles.backtesting_44_metrics.compute import _core_metrics


def _rets():
    rng = np.random.default_rng(3)
    return rng.normal(0.004, 0.02, 72)  # 72 daily returns, a strong short run


def test_sharpe_is_the_textbook_formula_not_cagr_over_vol():
    r = _rets()
    m = _core_metrics(r, "1D")
    expected = r.mean() / r.std() * np.sqrt(252)
    assert m["sharpe_ratio"] == pytest.approx(expected, abs=1e-3)


def test_a_short_strong_window_does_not_inflate_sharpe_but_the_old_ratio_stays_visible():
    m = _core_metrics(_rets(), "1D")
    strong = _core_metrics(np.random.default_rng(11).normal(0.0052, 0.0185, 72), "1D")  # MSFT-like: ~+40% in 72 days
    assert strong["total_return"] > 0.3
    assert strong["cagr_over_vol"] > strong["sharpe_ratio"] * 1.4  # compounding 72 days to a year
    assert m["cagr_over_vol"] == pytest.approx(m["cagr"] / m["ann_vol"], abs=1e-3)


def test_sortino_uses_downside_deviation_of_all_returns():
    r = _rets()
    m = _core_metrics(r, "1D")
    dd = np.sqrt(np.mean(np.minimum(r, 0) ** 2)) * np.sqrt(252)
    assert m["sortino_ratio"] == pytest.approx(r.mean() * 252 / dd, abs=1e-3)
