from vinu_strategy.engine.rules_engine import RulesEngine


class TestRulesEngine:
    def test_no_rules(self):
        engine = RulesEngine([])
        weight, trace = engine.evaluate(1.0, {})
        assert weight == 1.0
        assert trace == []

    def test_weight_add(self):
        rules = [
            {
                "name": "test_add",
                "when": [{"source": "features", "key": "RSI_14", "lt": 30}],
                "then": {"action": "weight_add", "value": 0.10},
            }
        ]
        engine = RulesEngine(rules)
        ctx = {"features": {"RSI_14": 25}}
        weight, trace = engine.evaluate(0.5, ctx)
        assert abs(weight - 0.6) < 0.001
        assert len(trace) == 1
        assert trace[0]["fired"] is True

    def test_weight_set(self):
        rules = [
            {
                "name": "test_set",
                "when": [{"source": "correlation", "key": "drawdown_count", "gt": 1}],
                "then": {"action": "weight_set", "value": 0.0},
            }
        ]
        engine = RulesEngine(rules)
        ctx = {"correlation": {"drawdown_count": 3}}
        weight, trace = engine.evaluate(0.5, ctx)
        assert weight == 0.0
        assert trace[0]["fired"] is True

    def test_condition_not_met(self):
        rules = [
            {
                "name": "test_no_fire",
                "when": [{"source": "features", "key": "RSI_14", "gt": 70}],
                "then": {"action": "weight_set", "value": 0.0},
            }
        ]
        engine = RulesEngine(rules)
        ctx = {"features": {"RSI_14": 50}}
        weight, trace = engine.evaluate(0.5, ctx)
        assert weight == 0.5
        assert trace[0]["fired"] is False

    def test_trace_conditions(self):
        rules = [
            {
                "name": "test_trace",
                "when": [
                    {"source": "features", "key": "ADX_14", "gt": 25},
                    {"source": "correlation", "key": "high_impact_bullish_events", "gt": 0},
                ],
                "then": {"action": "weight_multiply", "value": 1.20},
            }
        ]
        engine = RulesEngine(rules)
        ctx = {"features": {"ADX_14": 30}, "correlation": {"high_impact_bullish_events": 2}}
        weight, trace = engine.evaluate(1.0, ctx)
        assert len(trace) == 1
        assert trace[0]["fired"] is True
        assert len(trace[0]["conditions"]) == 2
        assert trace[0]["conditions"][0]["met"] is True
        assert trace[0]["conditions"][1]["met"] is True

    def test_trace_partial_fail(self):
        rules = [
            {
                "name": "partial",
                "when": [
                    {"source": "features", "key": "RSI_14", "lt": 30},
                    {"source": "features", "key": "ADX_14", "gt": 25},
                ],
                "then": {"action": "weight_set", "value": 0.0},
            }
        ]
        engine = RulesEngine(rules)
        ctx = {"features": {"RSI_14": 20, "ADX_14": 10}}
        weight, trace = engine.evaluate(0.5, ctx)
        assert weight == 0.5  # not fired
        assert trace[0]["fired"] is False
        c0 = trace[0]["conditions"][0]
        assert c0["met"] is True  # RSI_14 < 30: true
        c1 = trace[0]["conditions"][1]
        assert c1["met"] is False  # ADX_14 > 25: false

    def test_missing_context_key(self):
        rules = [
            {
                "name": "test_missing",
                "when": [{"source": "features", "key": "MISSING", "gt": 0}],
                "then": {"action": "weight_set", "value": 0.0},
            }
        ]
        engine = RulesEngine(rules)
        ctx = {"features": {"RSI": 50}}
        weight, trace = engine.evaluate(1.0, ctx)
        assert weight == 1.0
        assert trace[0]["fired"] is False
        assert "not found" in trace[0]["conditions"][0]["reason"]

    def test_multiple_rules(self):
        rules = [
            {
                "name": "rule1",
                "when": [{"source": "features", "key": "RSI_14", "lt": 30}],
                "then": {"action": "weight_add", "value": 0.10},
            },
            {
                "name": "rule2",
                "when": [{"source": "correlation", "key": "drawdown_count", "gt": 1}],
                "then": {"action": "weight_set", "value": 0.0},
            },
        ]
        engine = RulesEngine(rules)
        ctx = {"features": {"RSI_14": 25}, "correlation": {"drawdown_count": 3}}
        weight, trace = engine.evaluate(0.5, ctx)
        assert weight == 0.0  # rule2 sets to 0
        assert trace[0]["fired"] is True  # rule1 fired
        assert trace[1]["fired"] is True  # rule2 fired
