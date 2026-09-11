from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from vinu_screener.conditions.evaluator import evaluate
from vinu_screener.conditions.schema import parse_condition
from vinu_screener.features.library import FeatureLibrary


def _trending_up(n: int = 60) -> pd.DataFrame:
    close = np.linspace(100, 160, n)
    return pd.DataFrame({
        "open": close, "high": close + 0.5, "low": close - 0.5, "close": close,
        "volume": np.full(n, 10_000.0),
    })


def _flat(n: int = 60, level: float = 100.0) -> pd.DataFrame:
    close = np.full(n, level)
    return pd.DataFrame({
        "open": close, "high": close, "low": close, "close": close, "volume": np.full(n, 1000.0),
    })


class TestSimpleComparisons:
    def test_greater_than_true(self) -> None:
        df = _trending_up()
        node = parse_condition({"indicator": "close", "operator": ">", "value": 100})
        assert evaluate(node, df, FeatureLibrary(), "X") is True

    def test_greater_than_false(self) -> None:
        df = _trending_up()
        node = parse_condition({"indicator": "close", "operator": "<", "value": 1})
        assert evaluate(node, df, FeatureLibrary(), "X") is False

    def test_offset_reads_an_earlier_bar(self) -> None:
        df = _trending_up()
        latest = df["close"].iloc[-1]
        ago5 = df["close"].iloc[-6]
        node = parse_condition({"indicator": "close", "operator": ">", "value": (latest + ago5) / 2, "offset": 5})
        assert evaluate(node, df, FeatureLibrary(), "X") is False  # ago5 < midpoint (rising series)


class TestIndicatorVsIndicator:
    def test_close_crosses_above_its_own_sma(self) -> None:
        # flat at 100 (SMA settles at 100), dip below on the second-to-last
        # bar, jump back above on the last bar -- a crossing exactly at the
        # bar boundary the evaluator reads (not just "crossed somewhere
        # earlier in the series", which crosses_above must NOT fire on).
        close = np.array([100.0] * 30 + [95.0, 110.0])
        df = pd.DataFrame({"open": close, "high": close, "low": close, "close": close,
                           "volume": np.full(len(close), 1000.0)})
        node = parse_condition({
            "indicator": "close", "operator": "crosses_above",
            "compare_mode": "indicator", "compare_indicator": "sma", "compare_params": {"period": 10},
        })
        assert evaluate(node, df, FeatureLibrary(), "X") is True

    def test_no_cross_when_already_above(self) -> None:
        df = _trending_up()  # monotonic rise, already above its own rising SMA most of the time
        node = parse_condition({
            "indicator": "close", "operator": "crosses_above",
            "compare_mode": "indicator", "compare_indicator": "sma", "compare_params": {"period": 5},
        })
        # a monotonically rising series' close is *always* above a lagging SMA,
        # so there's no fresh crossing event at the last bar
        assert evaluate(node, df, FeatureLibrary(), "X") is False


class TestNonFiniteGuard:
    def test_leaf_fails_closed_on_non_finite_operand(self) -> None:
        close = np.array([100.0] * 10 + [0.0] + [100.0] * 10)  # a zero -> pct_change has an inf
        df = pd.DataFrame({"open": close, "high": close, "low": close, "close": close,
                           "volume": np.full(len(close), 1000.0)})
        node = parse_condition({"indicator": "pct_change", "operator": ">", "value": 0})
        # right at the bar after the zero, pct_change is +inf -- must not evaluate True
        # (evaluated at the last bar; construct so the last close follows a zero)
        result = evaluate(node, df.iloc[:12], FeatureLibrary(), "X")
        assert result is False

    def test_insufficient_history_for_the_indicator_fails_closed(self) -> None:
        df = _flat(n=5)
        node = parse_condition({"indicator": "sma", "operator": ">", "value": 0, "params": {"period": 50}})
        assert evaluate(node, df, FeatureLibrary(), "X") is False

    def test_unknown_indicator_fails_closed_not_raises(self) -> None:
        df = _trending_up()
        node = parse_condition({"indicator": "totally_made_up", "operator": ">", "value": 0})
        assert evaluate(node, df, FeatureLibrary(), "X") is False


class TestLevelTouch:
    def test_within_tolerance_is_a_touch(self) -> None:
        df = _flat(level=100.0)
        node = parse_condition({"indicator": "close", "operator": "==", "value": 100.0000001})
        assert evaluate(node, df, FeatureLibrary(), "X") is True

    def test_far_from_level_is_not_a_touch(self) -> None:
        df = _flat(level=100.0)
        node = parse_condition({"indicator": "close", "operator": "==", "value": 50.0})
        assert evaluate(node, df, FeatureLibrary(), "X") is False

    def test_sign_flip_between_bars_counts_as_a_touch(self) -> None:
        close = np.array([98.0] * 20 + [102.0])  # crossed through 100 between polls
        df = pd.DataFrame({"open": close, "high": close, "low": close, "close": close,
                           "volume": np.full(len(close), 1000.0)})
        node = parse_condition({"indicator": "close", "operator": "==", "value": 100.0})
        assert evaluate(node, df, FeatureLibrary(), "X") is True

    def test_not_equal_is_the_negation(self) -> None:
        df = _flat(level=100.0)
        node = parse_condition({"indicator": "close", "operator": "!=", "value": 100.0})
        assert evaluate(node, df, FeatureLibrary(), "X") is False


class TestRisingFalling:
    def test_rising_true_on_a_rising_series(self) -> None:
        df = _trending_up()
        node = parse_condition({"indicator": "close", "operator": "rising", "value": 0})
        assert evaluate(node, df, FeatureLibrary(), "X") is True

    def test_falling_false_on_a_rising_series(self) -> None:
        df = _trending_up()
        node = parse_condition({"indicator": "close", "operator": "falling", "value": 0})
        assert evaluate(node, df, FeatureLibrary(), "X") is False


class TestGroups:
    def test_and_short_circuits_on_first_false(self) -> None:
        df = _trending_up()
        node = parse_condition({
            "logic": "AND",
            "children": [
                {"indicator": "close", "operator": ">", "value": 1_000_000},  # false
                {"indicator": "close", "operator": ">", "value": 0},           # true
            ],
        })
        assert evaluate(node, df, FeatureLibrary(), "X") is False

    def test_or_true_if_any_child_true(self) -> None:
        df = _trending_up()
        node = parse_condition({
            "logic": "OR",
            "children": [
                {"indicator": "close", "operator": ">", "value": 1_000_000},  # false
                {"indicator": "close", "operator": ">", "value": 0},           # true
            ],
        })
        assert evaluate(node, df, FeatureLibrary(), "X") is True

    def test_negate_flips_the_group_result(self) -> None:
        df = _trending_up()
        node = parse_condition({
            "negate": True,
            "children": [{"indicator": "close", "operator": ">", "value": 0}],  # true, negated -> false
        })
        assert evaluate(node, df, FeatureLibrary(), "X") is False

    def test_nested_and_or(self) -> None:
        df = _trending_up()
        node = parse_condition({
            "logic": "AND",
            "children": [
                {"indicator": "close", "operator": ">", "value": 0},
                {"logic": "OR", "children": [
                    {"indicator": "close", "operator": "<", "value": 0},
                    {"indicator": "close", "operator": ">", "value": 0},
                ]},
            ],
        })
        assert evaluate(node, df, FeatureLibrary(), "X") is True

    def test_flat_legacy_list_evaluates_as_and(self) -> None:
        df = _trending_up()
        node = parse_condition([
            {"indicator": "close", "operator": ">", "value": 0},
            {"indicator": "close", "operator": ">", "value": 1},
        ])
        assert evaluate(node, df, FeatureLibrary(), "X") is True


class TestSharedLibraryCacheAcrossLeaves:
    def test_two_leaves_referencing_the_same_indicator_hit_the_cache(self) -> None:
        df = _trending_up()
        lib = FeatureLibrary()
        node = parse_condition({
            "logic": "AND",
            "children": [
                {"indicator": "sma", "operator": ">", "value": 0, "params": {"period": 10}},
                {"indicator": "sma", "operator": "<", "value": 1_000_000, "params": {"period": 10}},
            ],
        })
        evaluate(node, df, lib, "X")
        assert len(lib._cache) == 1  # both leaves shared one computed Series
