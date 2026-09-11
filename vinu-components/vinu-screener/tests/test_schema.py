from __future__ import annotations

import pytest

from vinu_screener.conditions.schema import (
    ConditionGroup,
    ConditionLeaf,
    ConditionSchemaError,
    op_needs_prev,
    parse_condition,
    walk,
)


class TestConditionLeaf:
    def test_minimal_leaf_parses(self) -> None:
        leaf = ConditionLeaf.from_dict({"indicator": "rsi", "operator": ">", "value": 70})
        assert leaf.indicator == "rsi"
        assert leaf.operator == ">"
        assert leaf.value == 70.0
        assert leaf.offset == 0
        assert leaf.compare_mode == "value"

    def test_full_leaf_with_indicator_compare_mode(self) -> None:
        leaf = ConditionLeaf.from_dict({
            "indicator": "close", "operator": "crosses_above", "offset": 0,
            "compare_mode": "indicator", "compare_indicator": "sma",
            "compare_params": {"period": 20}, "compare_offset": 0,
        })
        assert leaf.compare_mode == "indicator"
        assert leaf.compare_indicator == "sma"
        assert leaf.compare_params == {"period": 20}

    def test_unknown_operator_rejected(self) -> None:
        with pytest.raises(ConditionSchemaError):
            ConditionLeaf.from_dict({"indicator": "rsi", "operator": "wat", "value": 1})

    def test_negative_offset_rejected(self) -> None:
        with pytest.raises(ConditionSchemaError):
            ConditionLeaf.from_dict({"indicator": "rsi", "operator": ">", "value": 1, "offset": -1})

    def test_value_mode_requires_value(self) -> None:
        with pytest.raises(ConditionSchemaError):
            ConditionLeaf.from_dict({"indicator": "rsi", "operator": ">"})

    def test_indicator_mode_requires_compare_indicator(self) -> None:
        with pytest.raises(ConditionSchemaError):
            ConditionLeaf.from_dict({"indicator": "close", "operator": ">", "compare_mode": "indicator"})

    def test_missing_indicator_field_raises_schema_error_not_keyerror(self) -> None:
        with pytest.raises(ConditionSchemaError):
            ConditionLeaf.from_dict({"operator": ">", "value": 1})

    def test_roundtrip_to_dict_from_dict(self) -> None:
        leaf = ConditionLeaf.from_dict({"indicator": "rsi", "operator": ">", "value": 70, "params": {"period": 14}})
        again = ConditionLeaf.from_dict(leaf.to_dict())
        assert again == leaf


class TestConditionGroup:
    def test_and_group_of_two_leaves(self) -> None:
        raw = {
            "logic": "AND",
            "children": [
                {"indicator": "rsi", "operator": ">", "value": 30},
                {"indicator": "rsi", "operator": "<", "value": 70},
            ],
        }
        group = ConditionGroup.from_dict(raw)
        assert group.logic == "AND"
        assert len(group.children) == 2
        assert all(isinstance(c, ConditionLeaf) for c in group.children)

    def test_nested_group(self) -> None:
        raw = {
            "logic": "OR",
            "children": [
                {"logic": "AND", "children": [
                    {"indicator": "rsi", "operator": ">", "value": 30},
                    {"indicator": "rsi", "operator": "<", "value": 70},
                ]},
                {"indicator": "close", "operator": ">", "value": 100},
            ],
        }
        group = ConditionGroup.from_dict(raw)
        assert isinstance(group.children[0], ConditionGroup)
        assert isinstance(group.children[1], ConditionLeaf)

    def test_empty_children_rejected(self) -> None:
        with pytest.raises(ConditionSchemaError):
            ConditionGroup.from_dict({"logic": "AND", "children": []})

    def test_bad_logic_rejected(self) -> None:
        with pytest.raises(ConditionSchemaError):
            ConditionGroup.from_dict({"logic": "XOR", "children": [{"indicator": "rsi", "operator": ">", "value": 1}]})

    def test_negate_defaults_false(self) -> None:
        group = ConditionGroup.from_dict({"children": [{"indicator": "rsi", "operator": ">", "value": 1}]})
        assert group.negate is False


class TestParseCondition:
    def test_flat_legacy_list_becomes_implicit_and_group(self) -> None:
        raw = [
            {"indicator": "rsi", "operator": ">", "value": 30},
            {"indicator": "rsi", "operator": "<", "value": 70},
        ]
        node = parse_condition(raw)
        assert isinstance(node, ConditionGroup)
        assert node.logic == "AND"
        assert len(node.children) == 2

    def test_empty_flat_list_rejected(self) -> None:
        with pytest.raises(ConditionSchemaError):
            parse_condition([])

    def test_bare_dict_leaf(self) -> None:
        node = parse_condition({"indicator": "rsi", "operator": ">", "value": 30})
        assert isinstance(node, ConditionLeaf)

    def test_not_a_dict_or_list_rejected(self) -> None:
        with pytest.raises(ConditionSchemaError):
            parse_condition("nope")


class TestWalk:
    def test_walk_yields_every_leaf_depth_first(self) -> None:
        raw = {
            "logic": "OR",
            "children": [
                {"logic": "AND", "children": [
                    {"indicator": "a", "operator": ">", "value": 1},
                    {"indicator": "b", "operator": ">", "value": 2},
                ]},
                {"indicator": "c", "operator": ">", "value": 3},
            ],
        }
        node = parse_condition(raw)
        names = [leaf.indicator for leaf in walk(node)]
        assert names == ["a", "b", "c"]

    def test_walk_a_single_leaf(self) -> None:
        leaf = ConditionLeaf.from_dict({"indicator": "rsi", "operator": ">", "value": 1})
        assert list(walk(leaf)) == [leaf]


class TestOpNeedsPrev:
    def test_crossing_and_direction_ops_need_prev(self) -> None:
        for op in ("crosses_above", "crosses_below", "rising", "falling"):
            assert op_needs_prev(op) is True

    def test_simple_ops_do_not(self) -> None:
        for op in (">", "<", ">=", "<=", "==", "!="):
            assert op_needs_prev(op) is False
