from vinu_live.execution import (
    compute_volume_profile,
    plan_twap,
    plan_vwap,
    schedule_slice_delays,
)
from vinu_live.signal_translator import OrderInstruction


def _bar(bar_ts: int, volume: float) -> dict:
    return {"bar_ts": bar_ts, "volume": volume}


class TestComputeVolumeProfile:
    def test_empty_bars_falls_back_to_equal_weights(self) -> None:
        profile = compute_volume_profile([], n_slices=4)
        assert profile == [0.25, 0.25, 0.25, 0.25]

    def test_single_day_u_shaped_volume(self) -> None:
        day_start = 1_700_000_000
        bars = [
            _bar(day_start + i * 60, v)
            for i, v in enumerate([100, 10, 10, 10, 100])
        ]
        profile = compute_volume_profile(bars, n_slices=5)
        assert len(profile) == 5
        assert abs(sum(profile) - 1.0) < 1e-9
        assert profile[0] > profile[2]
        assert profile[4] > profile[2]

    def test_averages_across_multiple_days(self) -> None:
        day1 = 1_700_000_000
        day2 = day1 + 86_400
        bars = [_bar(day1 + i * 60, 100) for i in range(4)] + [_bar(day2 + i * 60, 100) for i in range(4)]
        profile = compute_volume_profile(bars, n_slices=4)
        assert all(abs(p - 0.25) < 1e-9 for p in profile)


class TestPlanVwap:
    def test_falls_back_to_equal_split_when_no_volume_data(self) -> None:
        instrs = [OrderInstruction(symbol="AAPL", side="buy", qty=100.0, target_weight=0.5, current_qty=0.0, estimated_value=10000.0)]
        plan = plan_vwap(instrs, volume_weights=None, n_slices=4)
        assert plan.total_orders == 4
        assert sum(s.qty for s in plan.slices) == 100.0
        assert all(s.qty == 25.0 for s in plan.slices)

    def test_uses_provided_weights_and_sums_to_total_qty(self) -> None:
        instrs = [OrderInstruction(symbol="AAPL", side="buy", qty=100.0, target_weight=0.5, current_qty=0.0, estimated_value=10000.0)]
        plan = plan_vwap(instrs, volume_weights={"AAPL": [0.4, 0.3, 0.2, 0.1]}, n_slices=4)
        qtys = [s.qty for s in plan.slices]
        assert qtys[0] == 40.0
        assert abs(sum(qtys) - 100.0) < 1e-6

    def test_falls_back_when_weights_wrong_length(self) -> None:
        instrs = [OrderInstruction(symbol="AAPL", side="buy", qty=100.0, target_weight=0.5, current_qty=0.0, estimated_value=10000.0)]
        plan = plan_vwap(instrs, volume_weights={"AAPL": [1.0, 1.0]}, n_slices=4)
        assert all(s.qty == 25.0 for s in plan.slices)

    def test_missing_symbol_falls_back_to_equal(self) -> None:
        instrs = [OrderInstruction(symbol="MSFT", side="sell", qty=40.0, target_weight=0.0, current_qty=40.0, estimated_value=4000.0)]
        plan = plan_vwap(instrs, volume_weights={"AAPL": [0.4, 0.3, 0.2, 0.1]}, n_slices=4)
        assert all(s.qty == 10.0 for s in plan.slices)


class TestPlanTwapUnchanged:
    def test_still_splits_equally(self) -> None:
        instrs = [OrderInstruction(symbol="AAPL", side="buy", qty=60.0, target_weight=0.5, current_qty=0.0, estimated_value=6000.0)]
        plan = plan_twap(instrs, n_slices=6)
        assert plan.total_orders == 6
        assert all(s.qty == 10.0 for s in plan.slices)


class TestScheduleSliceDelays:
    def test_returns_n_minus_one_delays(self) -> None:
        delays = schedule_slice_delays(6, total_window_minutes=60)
        assert len(delays) == 5
        assert sum(delays) <= 3600
