import pytest

from vinu_live.trade_plan.condition_evaluator import evaluate_condition, find_triggered_rules


class TestEvaluateCondition:
    @pytest.mark.parametrize(
        "value,operator,threshold,expected",
        [
            (0.06, ">=", 0.05, True),
            (0.04, ">=", 0.05, False),
            (0.05, ">=", 0.05, True),
            (0.02, "<=", 0.05, True),
            (0.06, "<=", 0.05, False),
            (0.06, ">", 0.05, True),
            (0.05, ">", 0.05, False),
            (0.04, "<", 0.05, True),
            (0.05, "==", 0.05, True),
            (0.05, "!=", 0.05, False),
        ],
    )
    def test_operators(self, value, operator, threshold, expected) -> None:
        assert evaluate_condition(value, operator, threshold) is expected

    def test_unknown_operator_never_triggers(self) -> None:
        assert evaluate_condition(1.0, "~=", 0.5) is False


class TestFindTriggeredRules:
    def test_returns_only_triggered(self) -> None:
        rules = [
            {"metric": "drawdown_pct", "operator": ">=", "threshold": 0.05, "action": "reduce_position"},
            {"metric": "unrealized_pnl_pct", "operator": "<=", "threshold": -0.5, "action": "exit"},
        ]
        metrics = {"drawdown_pct": 0.08, "unrealized_pnl_pct": -0.02}
        triggered = find_triggered_rules(rules, metrics)
        assert len(triggered) == 1
        assert triggered[0]["action"] == "reduce_position"

    def test_missing_metric_never_triggers(self) -> None:
        rules = [{"metric": "shock_cluster_correlation", "operator": ">=", "threshold": 0.7, "action": "reduce_position"}]
        triggered = find_triggered_rules(rules, {})
        assert triggered == []

    def test_empty_rules_returns_empty(self) -> None:
        assert find_triggered_rules([], {"drawdown_pct": 0.5}) == []

    def test_multiple_rules_can_all_trigger(self) -> None:
        rules = [
            {"metric": "drawdown_pct", "operator": ">=", "threshold": 0.05, "action": "reduce_position"},
            {"metric": "drawdown_pct", "operator": ">=", "threshold": 0.03, "action": "tighten_stop"},
        ]
        triggered = find_triggered_rules(rules, {"drawdown_pct": 0.08})
        assert len(triggered) == 2
