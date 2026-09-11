from __future__ import annotations

from vinu_screener.conditions.lookback import (
    MIN_REQUIRED_BARS,
    leaf_required_bars,
    required_bars,
)
from vinu_screener.conditions.schema import parse_condition


class TestLeafRequiredBars:
    def test_no_period_no_offset_is_the_unconditional_plus_two_margin(self) -> None:
        # period defaults to 1 (just the current bar), offset 0 -> 1 + 0 + 2 = 3.
        # The fixed "+2" margin (covers the one-bar-back crossing operators need)
        # is applied unconditionally, per FinceptTerminal's own formula.
        leaf = parse_condition({"indicator": "close", "operator": ">", "value": 100})
        assert leaf_required_bars(leaf) == 3
        assert leaf_required_bars(leaf) >= MIN_REQUIRED_BARS

    def test_period_param_extends_lookback(self) -> None:
        leaf = parse_condition({"indicator": "sma", "operator": ">", "value": 1, "params": {"period": 20}})
        assert leaf_required_bars(leaf) == 20 + 0 + 2

    def test_offset_extends_lookback(self) -> None:
        leaf = parse_condition({"indicator": "rsi", "operator": ">", "value": 70, "offset": 5})
        assert leaf_required_bars(leaf) == 1 + 5 + 2

    def test_compare_indicator_period_counts_too(self) -> None:
        leaf = parse_condition({
            "indicator": "close", "operator": "crosses_above",
            "compare_mode": "indicator", "compare_indicator": "sma", "compare_params": {"period": 50},
        })
        assert leaf_required_bars(leaf) == max(1, 50) + 0 + 2

    def test_takes_the_max_of_own_and_compare_period(self) -> None:
        leaf = parse_condition({
            "indicator": "sma", "operator": ">", "params": {"period": 10},
            "compare_mode": "indicator", "compare_indicator": "sma", "compare_params": {"period": 200},
        })
        assert leaf_required_bars(leaf) == 200 + 2

    def test_multi_period_indicator_takes_the_largest_key(self) -> None:
        leaf = parse_condition({
            "indicator": "macd", "operator": ">", "value": 0,
            "params": {"fast": 12, "slow": 26, "signal_period": 9},
        })
        assert leaf_required_bars(leaf) == 26 + 0 + 2

    def test_value_literal_compare_mode_ignores_compare_params(self) -> None:
        leaf = parse_condition({
            "indicator": "close", "operator": ">", "value": 100,
            "compare_params": {"period": 999},  # ignored: compare_mode is "value"
        })
        assert leaf_required_bars(leaf) == 1 + 0 + 2


class TestRequiredBarsOverTree:
    def test_max_over_and_group(self) -> None:
        node = parse_condition({
            "logic": "AND",
            "children": [
                {"indicator": "sma", "operator": ">", "value": 1, "params": {"period": 20}},
                {"indicator": "sma", "operator": ">", "value": 1, "params": {"period": 200}},
            ],
        })
        assert required_bars(node) == 200 + 2

    def test_nested_group_still_finds_the_deepest_requirement(self) -> None:
        node = parse_condition({
            "logic": "OR",
            "children": [
                {"logic": "AND", "children": [
                    {"indicator": "close", "operator": ">", "value": 1},
                    {"indicator": "sma", "operator": ">", "value": 1, "params": {"period": 100}},
                ]},
                {"indicator": "close", "operator": ">", "value": 1},
            ],
        })
        assert required_bars(node) == 100 + 2

    def test_flat_legacy_list(self) -> None:
        node = parse_condition([
            {"indicator": "sma", "operator": ">", "value": 1, "params": {"period": 50}},
        ])
        assert required_bars(node) == 52
