from vinu_live.live_decision.conditions import evaluate_all


def test_empty_conditions_never_fire():
    fired, trace = evaluate_all([], {"live_indicators": {"adx_14": 30}})
    assert fired is False
    assert trace == []


def test_all_conditions_must_pass():
    conditions = [
        {"source": "live_indicators", "key": "adx_14", "operator": "gt", "value": 20},
        {"source": "live_indicators", "key": "rsi_14", "operator": "lt", "value": 70},
    ]
    fired, trace = evaluate_all(conditions, {"live_indicators": {"adx_14": 25, "rsi_14": 60}})
    assert fired is True
    assert len(trace) == 2
    assert all(r["met"] for r in trace)


def test_one_failing_condition_fails_the_whole_and():
    conditions = [
        {"source": "live_indicators", "key": "adx_14", "operator": "gt", "value": 20},
        {"source": "live_indicators", "key": "rsi_14", "operator": "lt", "value": 50},
    ]
    fired, trace = evaluate_all(conditions, {"live_indicators": {"adx_14": 25, "rsi_14": 60}})
    assert fired is False


def test_missing_key_is_not_met_not_an_error():
    conditions = [{"source": "live_indicators", "key": "does_not_exist", "operator": "gt", "value": 1}]
    fired, trace = evaluate_all(conditions, {"live_indicators": {"adx_14": 25}})
    assert fired is False
    assert trace[0]["actual"] is None


def test_between_operator():
    conditions = [{"source": "live_indicators", "key": "adx_14", "operator": "between", "value": [15, 20]}]
    fired, _ = evaluate_all(conditions, {"live_indicators": {"adx_14": 17.8}})
    assert fired is True


def test_nested_key_lookup():
    conditions = [{"source": "live_indicators", "key": "a.b", "operator": "eq", "value": 5}]
    fired, _ = evaluate_all(conditions, {"live_indicators": {"a": {"b": 5}}})
    assert fired is True
