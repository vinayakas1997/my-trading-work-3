import pytest

from vinu_live.book.schema import Position
from vinu_live.trade_plan.live_metrics import compute_live_metrics


def _long_position(avg_entry: float = 100.0, qty: float = 10.0) -> Position:
    return Position(
        position_id="pos_1", symbol="AAPL", side="long", qty=qty, avg_entry=avg_entry,
        opened_at="2026-07-27T00:00:00Z", updated_at="2026-07-27T00:00:00Z",
    )


class TestUnrealizedAndDrawdown:
    def test_profitable_position_has_zero_drawdown(self) -> None:
        pos = _long_position(avg_entry=100.0)
        metrics = compute_live_metrics(pos, current_price=110.0, plan={})
        assert metrics["unrealized_pnl_pct"] > 0
        assert metrics["drawdown_pct"] == 0.0

    def test_losing_position_has_positive_drawdown(self) -> None:
        pos = _long_position(avg_entry=100.0)
        metrics = compute_live_metrics(pos, current_price=90.0, plan={})
        assert metrics["unrealized_pnl_pct"] < 0
        assert metrics["drawdown_pct"] == pytest.approx(0.10)

    def test_short_position_losing_on_price_rise(self) -> None:
        pos = Position(
            position_id="pos_2", symbol="AAPL", side="short", qty=10.0, avg_entry=100.0,
            opened_at="2026-07-27T00:00:00Z", updated_at="2026-07-27T00:00:00Z",
        )
        metrics = compute_live_metrics(pos, current_price=110.0, plan={})
        assert metrics["unrealized_pnl_pct"] < 0
        assert metrics["drawdown_pct"] > 0


class TestGapAgainstPosition:
    def test_downside_gap_against_long(self) -> None:
        pos = _long_position()
        metrics = compute_live_metrics(pos, current_price=95.0, plan={}, previous_close=100.0)
        assert metrics["gap_against_position_pct"] == pytest.approx(0.05)

    def test_upside_move_not_counted_as_adverse_for_long(self) -> None:
        pos = _long_position()
        metrics = compute_live_metrics(pos, current_price=105.0, plan={}, previous_close=100.0)
        assert metrics["gap_against_position_pct"] == 0.0

    def test_no_previous_close_omits_metric(self) -> None:
        pos = _long_position()
        metrics = compute_live_metrics(pos, current_price=95.0, plan={})
        assert "gap_against_position_pct" not in metrics


class TestRealizedVolRatio:
    def test_omitted_without_recent_returns(self) -> None:
        pos = _long_position()
        plan = {"risk_bands": {"volatility_band_upper": 0.3}}
        metrics = compute_live_metrics(pos, current_price=100.0, plan=plan)
        assert "realized_vol_ratio" not in metrics

    def test_omitted_without_forecast_vol(self) -> None:
        pos = _long_position()
        returns = [0.01, -0.01] * 15
        metrics = compute_live_metrics(pos, current_price=100.0, plan={}, recent_returns=returns)
        assert "realized_vol_ratio" not in metrics

    def test_present_with_both_inputs(self) -> None:
        pos = _long_position()
        plan = {"risk_bands": {"volatility_band_upper": 0.3}}
        returns = [0.02, -0.015, 0.01, -0.02, 0.015] * 6
        metrics = compute_live_metrics(pos, current_price=100.0, plan=plan, recent_returns=returns)
        assert "realized_vol_ratio" in metrics
        assert metrics["realized_vol_ratio"] > 0


class TestRealizedMoveVsForecastStd:
    def test_present_when_forecast_has_magnitude_std(self) -> None:
        pos = _long_position(avg_entry=100.0)
        plan = {"forecast": {"magnitude_std": 0.02}}
        metrics = compute_live_metrics(pos, current_price=98.0, plan=plan)
        assert metrics["realized_move_vs_forecast_std"] == pytest.approx(1.0)

    def test_omitted_without_forecast(self) -> None:
        pos = _long_position()
        metrics = compute_live_metrics(pos, current_price=98.0, plan={})
        assert "realized_move_vs_forecast_std" not in metrics


class TestShockClusterCorrelation:
    def test_included_when_provided(self) -> None:
        pos = _long_position()
        metrics = compute_live_metrics(pos, current_price=100.0, plan={}, shock_cluster_correlation=0.85)
        assert metrics["shock_cluster_correlation"] == 0.85

    def test_omitted_when_none(self) -> None:
        pos = _long_position()
        metrics = compute_live_metrics(pos, current_price=100.0, plan={})
        assert "shock_cluster_correlation" not in metrics
