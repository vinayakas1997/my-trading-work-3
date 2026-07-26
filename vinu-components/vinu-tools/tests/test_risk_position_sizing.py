import numpy as np
from vinu_tools.compute.risk.position_sizing import (
    kelly_optimal_fraction,
    risk_budget_position_size,
    volatility_parity_weights,
    max_position_size_from_risk_budget,
)


def test_kelly_fair_coin():
    f = kelly_optimal_fraction(win_rate=0.5, avg_win=1.0, avg_loss=1.0)
    assert f == 0.0  # no edge


def test_kelly_with_edge():
    f = kelly_optimal_fraction(win_rate=0.6, avg_win=1.0, avg_loss=1.0)
    assert f > 0.0
    assert f < 1.0


def test_kelly_fraction_of_kelly():
    full = kelly_optimal_fraction(win_rate=0.6, avg_win=1.0, avg_loss=1.0)
    half = kelly_optimal_fraction(win_rate=0.6, avg_win=1.0, avg_loss=1.0, fraction_of_kelly=0.5)
    assert abs(half - full * 0.5) < 1e-10


def test_risk_budget_stop_loss():
    size = risk_budget_position_size(
        risk_budget=1000, entry_price=100, stop_price=95, method="stop_loss"
    )
    assert size == 200.0  # 1000 / 5


def test_risk_budget_volatility():
    size = risk_budget_position_size(
        risk_budget=1000, entry_price=100, stop_price=0,
        volatility=0.02, z_score=2.0, method="volatility"
    )
    expected = 1000 / (100 * 0.02 * 2)
    assert abs(size - expected) < 0.01


def test_volatility_parity_weights():
    vols = np.array([0.2, 0.4, 0.1])
    weights = volatility_parity_weights(vols)
    assert abs(np.sum(weights) - 1.0) < 1e-10
    assert weights[0] > weights[1]  # lower vol -> higher weight


def test_volatility_parity_equal():
    vols = np.array([0.2, 0.2, 0.2])
    weights = volatility_parity_weights(vols)
    assert np.allclose(weights, 1/3)


def test_max_position_size():
    size = max_position_size_from_risk_budget(
        portfolio_value=100000, risk_budget_pct=0.02,
        symbol_volatility=0.20, holding_period_days=1,
    )
    assert 0 < size < 100000


def test_max_position_size_zero_vol():
    size = max_position_size_from_risk_budget(
        portfolio_value=100000, risk_budget_pct=0.02,
        symbol_volatility=0.0, holding_period_days=1,
    )
    assert size >= 0
