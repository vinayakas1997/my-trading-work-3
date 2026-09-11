from __future__ import annotations

import math

from vinu_screener.scan.universe import CoarseFilter, coarse_select, passes_coarse


class TestPassesCoarse:
    def test_empty_filter_passes_everything(self) -> None:
        assert passes_coarse({"price": 1.0}, CoarseFilter()) is True
        assert passes_coarse({}, CoarseFilter()) is True

    def test_min_price(self) -> None:
        f = CoarseFilter(min_price=5.0)
        assert passes_coarse({"price": 10.0}, f) is True
        assert passes_coarse({"price": 1.0}, f) is False

    def test_max_price(self) -> None:
        f = CoarseFilter(max_price=100.0)
        assert passes_coarse({"price": 50.0}, f) is True
        assert passes_coarse({"price": 500.0}, f) is False

    def test_min_volume(self) -> None:
        f = CoarseFilter(min_volume=1000.0)
        assert passes_coarse({"volume": 5000.0}, f) is True
        assert passes_coarse({"volume": 10.0}, f) is False

    def test_min_dollar_volume(self) -> None:
        f = CoarseFilter(min_dollar_volume=1_000_000.0)
        assert passes_coarse({"dollar_volume": 2_000_000.0}, f) is True
        assert passes_coarse({"dollar_volume": 100.0}, f) is False

    def test_missing_field_fails_closed(self) -> None:
        f = CoarseFilter(min_price=1.0)
        assert passes_coarse({}, f) is False  # no "price" key at all

    def test_non_finite_field_fails_closed(self) -> None:
        f = CoarseFilter(min_price=1.0)
        assert passes_coarse({"price": float("nan")}, f) is False
        assert passes_coarse({"price": float("inf")}, f) is False

    def test_all_bounds_combined(self) -> None:
        f = CoarseFilter(min_price=10.0, max_price=500.0, min_volume=1000.0, min_dollar_volume=50_000.0)
        good = {"price": 50.0, "volume": 2000.0, "dollar_volume": 100_000.0}
        assert passes_coarse(good, f) is True
        assert passes_coarse({**good, "price": 5.0}, f) is False


class TestCoarseSelect:
    def test_selects_only_survivors_in_input_order(self) -> None:
        universe = {
            "AAPL": {"price": 150.0, "volume": 1_000_000.0, "dollar_volume": 150_000_000.0},
            "PENNY": {"price": 0.50, "volume": 100.0, "dollar_volume": 50.0},
            "MSFT": {"price": 300.0, "volume": 500_000.0, "dollar_volume": 150_000_000.0},
        }
        survivors = coarse_select(universe, CoarseFilter(min_price=1.0, min_dollar_volume=1_000_000.0))
        assert survivors == ["AAPL", "MSFT"]

    def test_empty_universe(self) -> None:
        assert coarse_select({}, CoarseFilter(min_price=1.0)) == []

    def test_no_op_filter_returns_everyone(self) -> None:
        universe = {"A": {"price": 1.0}, "B": {"price": 2.0}}
        assert coarse_select(universe, CoarseFilter()) == ["A", "B"]
