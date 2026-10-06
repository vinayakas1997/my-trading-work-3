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
    expected = r.mean() / r.std(ddof=1) * np.sqrt(252)  # sample std, same as the simulator
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


def test_a_fall_right_after_the_first_bar_counts_toward_max_drawdown():
    """Price 100 -> 80 on day 2, then flat: the max drawdown is -20%. Without the
    starting price as a peak it read 0."""
    m = _core_metrics(np.array([-0.20, 0.0, 0.0, 0.0]), "1D")
    assert m["max_drawdown"] == pytest.approx(-0.20, abs=1e-6)


def test_the_angle_and_the_simulator_report_the_same_sharpe_for_the_same_returns():
    """One Sharpe definition across the system: the idea generator reads the
    angle's number and then the simulator's, and they must be comparable."""
    metrics = pytest.importorskip("vinu_simulator.engine.metrics")
    import pandas as pd

    r = _rets()
    angle = _core_metrics(r, "1D")["sharpe_ratio"]
    sim = metrics._get_basic_sharpe(pd.Series(100 * (1 + r).cumprod()), pd.Series(r), 0.0, 252.0)
    assert angle == pytest.approx(sim, abs=1e-3)
