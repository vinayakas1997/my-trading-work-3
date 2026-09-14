from __future__ import annotations

import logging

from vinu_portfolio.sizing import apply_position_sizing, vol_targeting_position_size


class TestVolTargetingPositionSize:
    def test_scales_down_when_realized_vol_exceeds_target(self) -> None:
        size = vol_targeting_position_size(risk_budget=1000.0, realized_vol=0.30, target_vol=0.15)
        assert size == 500.0

    def test_capped_by_max_leverage_when_realized_vol_below_target(self) -> None:
        size = vol_targeting_position_size(
            risk_budget=1000.0, realized_vol=0.05, target_vol=0.15, max_leverage=2.0,
        )
        assert size == 2000.0

    def test_zero_realized_vol_returns_risk_budget_unscaled(self) -> None:
        assert vol_targeting_position_size(risk_budget=1000.0, realized_vol=0.0) == 1000.0


class TestApplyPositionSizing:
    def test_scales_by_provided_vol_estimate(self) -> None:
        weights = [{"name": "strat_a", "target_weight": 0.5}]
        result = apply_position_sizing(
            weights, total_capital=10_000.0, target_vol=0.15,
            vol_estimates={"strat_a": 0.30},
        )
        assert result[0]["position_size"] == 2500.0  # 5000 * (0.15/0.30)

    def test_missing_vol_estimate_leaves_sizing_unscaled(self) -> None:
        weights = [{"name": "strat_b", "target_weight": 0.5}]
        result = apply_position_sizing(
            weights, total_capital=10_000.0, target_vol=0.15, vol_estimates={},
        )
        # vol defaults to target_vol -> ratio 1.0 -> unscaled dollar allocation
        assert result[0]["position_size"] == 5000.0

    def test_missing_vol_estimate_logs_warning(self, caplog) -> None:
        weights = [{"name": "strat_c", "target_weight": 0.5}]
        with caplog.at_level(logging.WARNING, logger="vinu_portfolio.sizing"):
            apply_position_sizing(weights, total_capital=10_000.0, vol_estimates={})
        assert any("strat_c" in r.message for r in caplog.records)

    def test_present_vol_estimate_does_not_log_warning(self, caplog) -> None:
        weights = [{"name": "strat_d", "target_weight": 0.5}]
        with caplog.at_level(logging.WARNING, logger="vinu_portfolio.sizing"):
            apply_position_sizing(
                weights, total_capital=10_000.0, vol_estimates={"strat_d": 0.2},
            )
        assert not caplog.records
