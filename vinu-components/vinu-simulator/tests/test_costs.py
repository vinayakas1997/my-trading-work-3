from __future__ import annotations

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
