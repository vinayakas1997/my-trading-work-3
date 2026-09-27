import logging

from vinu_strategy.engine.timing import run_timing, timing_none, timing_rules


class TestTimingNone:
    def test_passes_weights_through_unchanged(self):
        weights = {"AAPL": 0.5, "MSFT": 0.3}
        result, trace = timing_none(weights)
        assert result == weights
        assert trace == {}

    def test_ignores_signal_context_and_params(self):
        weights = {"AAPL": 0.5}
        result, trace = timing_none(weights, signal_context={"AAPL": {}}, params={"rules": []})
        assert result == weights
        assert trace == {}


class TestTimingRules:
    def test_no_rules_returns_weights_unchanged(self):
        weights = {"AAPL": 0.5, "MSFT": 0.3}
        result, trace = timing_rules(weights, signal_context={})
        assert result == weights
        assert trace == {}

    def test_missing_params_is_a_no_op(self):
        weights = {"AAPL": 0.5}
        result, trace = timing_rules(weights, signal_context={}, params=None)
        assert result == weights
        assert trace == {}

    def test_a_fired_rule_adjusts_only_the_matching_symbol(self):
        weights = {"AAPL": 0.5, "MSFT": 0.3}
        signal_context = {
            "AAPL": {"features": {"MOM_20": 2.0}},
            "MSFT": {"features": {"MOM_20": -1.0}},
        }
        params = {
            "rules": [
                {
                    "name": "boost_on_momentum",
                    "when": [{"source": "features", "key": "MOM_20", "gt": 0}],
                    "then": {"action": "weight_multiply", "value": 1.5},
                }
            ]
        }
        result, trace = timing_rules(weights, signal_context, params)
        assert abs(result["AAPL"] - 0.75) < 1e-9
        assert result["MSFT"] == 0.3
        assert trace["AAPL"][0]["fired"] is True
        assert trace["MSFT"][0]["fired"] is False

    def test_a_symbol_with_no_signal_context_still_gets_a_verdict(self):
        """A symbol absent from signal_context entirely (not just missing a
        specific key) must not crash -- the rule simply fails its
        condition against an empty context."""
        weights = {"AAPL": 0.5}
        params = {
            "rules": [
                {
                    "name": "boost_on_momentum",
                    "when": [{"source": "features", "key": "MOM_20", "gt": 0}],
                    "then": {"action": "weight_multiply", "value": 1.5},
                }
            ]
        }
        result, trace = timing_rules(weights, signal_context={}, params=params)
        assert result["AAPL"] == 0.5
        assert trace["AAPL"][0]["fired"] is False

    def test_multiple_rules_apply_in_order(self):
        weights = {"AAPL": 1.0}
        signal_context = {"AAPL": {"features": {"MOM_20": 1.0}}}
        params = {
            "rules": [
                {
                    "name": "add",
                    "when": [{"source": "features", "key": "MOM_20", "gt": 0}],
                    "then": {"action": "weight_add", "value": 0.5},
                },
                {
                    "name": "multiply",
                    "when": [{"source": "features", "key": "MOM_20", "gt": 0}],
                    "then": {"action": "weight_multiply", "value": 2.0},
                },
            ]
        }
        result, trace = timing_rules(weights, signal_context, params)
        # (1.0 + 0.5) * 2.0 == 3.0 -- proves rules chain, not just independently apply
        assert abs(result["AAPL"] - 3.0) < 1e-9
        assert len(trace["AAPL"]) == 2


class TestRunTiming:
    def test_dispatches_to_none(self):
        weights = {"AAPL": 0.5}
        result, trace = run_timing("none", weights)
        assert result == weights
        assert trace == {}

    def test_dispatches_to_rules(self):
        weights = {"AAPL": 1.0}
        signal_context = {"AAPL": {"features": {"MOM_20": 1.0}}}
        params = {
            "rules": [
                {
                    "name": "boost",
                    "when": [{"source": "features", "key": "MOM_20", "gt": 0}],
                    "then": {"action": "weight_multiply", "value": 1.5},
                }
            ]
        }
        result, trace = run_timing("rules", weights, signal_context, params)
        assert abs(result["AAPL"] - 1.5) < 1e-9

    def test_unknown_method_falls_back_to_weights_unchanged_and_warns(self, caplog):
        weights = {"AAPL": 0.5}
        with caplog.at_level(logging.WARNING):
            result, trace = run_timing("totally_made_up", weights)
        assert result == weights
        assert trace == {}
        assert "unknown timing method" in caplog.text.lower()
