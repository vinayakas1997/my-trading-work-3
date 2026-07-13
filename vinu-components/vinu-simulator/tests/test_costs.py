from __future__ import annotations

import pytest

from vinu_simulator.engine.costs import FlatCostModel, AlmgrenChrissCostModel


class TestFlatCostModel:
    def test_buy_cost(self):
        model = FlatCostModel(cost_pct=0.001, slippage_pct=0.0005)
        cost = model.buy_cost(price=100.0, shares=10.0)
        expected = 100.0 * 1.0005 * 10.0 * 1.001
        assert abs(cost - expected) < 1e-6

    def test_sell_proceeds(self):
        model = FlatCostModel(cost_pct=0.001, slippage_pct=0.0005)
        proceeds = model.sell_proceeds(price=100.0, shares=10.0)
        expected = 100.0 * 0.9995 * 10.0 * 0.999
        assert abs(proceeds - expected) < 1e-6

    def test_zero_cost(self):
        model = FlatCostModel(cost_pct=0.0, slippage_pct=0.0)
        cost = model.buy_cost(price=100.0, shares=10.0)
        assert cost == 1000.0
        proceeds = model.sell_proceeds(price=100.0, shares=10.0)
        assert proceeds == 1000.0


class TestAlmgrenChrissCostModel:
    def test_buy_cost_no_volume(self):
        model = AlmgrenChrissCostModel(fixed_cost_pct=0.001, slippage_pct=0.0005)
        cost = model.buy_cost(price=100.0, shares=10.0)
        assert cost > 1000.0  # with fees

    def test_buy_cost_with_volume(self):
        model = AlmgrenChrissCostModel()
        cost = model.buy_cost(price=100.0, shares=10.0, volume=1_000_000.0)
        assert cost > 1000.0
        assert cost < 1000.0 * 1.01  # small impact with high volume

    def test_sell_proceeds_with_volume(self):
        model = AlmgrenChrissCostModel()
        proceeds = model.sell_proceeds(price=100.0, shares=10.0, volume=1_000_000.0)
        assert proceeds < 1000.0
        assert proceeds > 1000.0 * 0.99

    def test_low_volume_high_impact(self):
        model = AlmgrenChrissCostModel(market_impact_coeff=0.1)
        low_vol = model.buy_cost(price=100.0, shares=1000.0, volume=5000.0)
        high_vol = model.buy_cost(price=100.0, shares=1000.0, volume=1_000_000.0)
        assert low_vol > high_vol  # lower volume = higher impact

    def test_missing_volume_charges_penalty_not_zero_impact(self):
        """
        Missing volume data is evidence of uncertainty, not proof a trade was free of
        market impact. A missing-volume trade must cost more than the same trade with
        ample volume, not the same or less.
        """
        model = AlmgrenChrissCostModel(missing_volume_impact_pct=0.005)
        no_volume = model.buy_cost(price=100.0, shares=10.0, volume=None)
        zero_volume = model.buy_cost(price=100.0, shares=10.0, volume=0.0)
        ample_volume = model.buy_cost(price=100.0, shares=10.0, volume=1_000_000.0)
        assert no_volume > ample_volume
        assert zero_volume > ample_volume

    def test_daily_borrow_cost_on_short_notional(self):
        model = AlmgrenChrissCostModel(borrow_cost_annual=0.0075)
        assert model.daily_borrow_cost(0.0) == 0.0
        cost = model.daily_borrow_cost(100_000.0)
        assert cost == pytest.approx(100_000.0 * 0.0075 / 252.0)

    def test_flat_model_also_has_borrow_cost(self):
        model = FlatCostModel(borrow_cost_annual=0.01)
        assert model.daily_borrow_cost(50_000.0) == pytest.approx(50_000.0 * 0.01 / 252.0)
