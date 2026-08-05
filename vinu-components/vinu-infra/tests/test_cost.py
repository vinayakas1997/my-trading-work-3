from vinu_infra.llm.cost import CostEntry, CostTracker, TokenUsage, get_global_cost_tracker


def test_token_usage_from_api_response_empty():
    usage = TokenUsage.from_api_response({})
    assert usage.prompt_tokens == 0
    assert usage.completion_tokens == 0
    assert usage.total_tokens == 0


def test_token_usage_from_api_response_with_data():
    data = {"usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}}
    usage = TokenUsage.from_api_response(data)
    assert usage.prompt_tokens == 10
    assert usage.completion_tokens == 20
    assert usage.total_tokens == 30


def test_token_usage_partial_data():
    data = {"usage": {"prompt_tokens": 5}}
    usage = TokenUsage.from_api_response(data)
    assert usage.prompt_tokens == 5
    assert usage.completion_tokens == 0
    assert usage.total_tokens == 0


def test_cost_tracker_record_and_summary():
    tracker = CostTracker()
    tracker.record(CostEntry(
        ts="2025-01-01T00:00:00Z", service="research", model="gpt-4",
        provider="openai", prompt_tokens=100, completion_tokens=50,
        total_tokens=150, estimated_cost_usd=0.010, duration_sec=1.5, success=True,
    ))
    tracker.record(CostEntry(
        ts="2025-01-01T00:00:01Z", service="research", model="gpt-4",
        provider="openai", prompt_tokens=200, completion_tokens=100,
        total_tokens=300, estimated_cost_usd=0.020, duration_sec=2.0, success=True,
    ))
    s = tracker.summary()
    assert s["total_calls"] == 2
    assert s["successful_calls"] == 2
    assert s["total_tokens"] == 450
    assert s["prompt_tokens"] == 300
    assert s["completion_tokens"] == 150
    assert s["total_cost_usd"] == 0.03


def test_cost_tracker_totals():
    tracker = CostTracker()
    tracker.record(CostEntry(
        ts="", service="s", model="m", provider="p",
        prompt_tokens=10, completion_tokens=5, total_tokens=15,
        estimated_cost_usd=0.001, duration_sec=0.5, success=True,
    ))
    assert tracker.total_calls == 1
    assert tracker.total_cost_usd == 0.001
    assert tracker.total_tokens == 15
    assert tracker.successful_calls == 1


def test_cost_tracker_failed_call():
    tracker = CostTracker()
    tracker.record(CostEntry(
        ts="", service="s", model="m", provider="p",
        prompt_tokens=0, completion_tokens=0, total_tokens=0,
        estimated_cost_usd=0.0, duration_sec=0.1, success=False,
    ))
    assert tracker.successful_calls == 0
    assert tracker.total_calls == 1


def test_cost_tracker_reset():
    tracker = CostTracker()
    tracker.record(CostEntry(
        ts="", service="s", model="m", provider="p",
        prompt_tokens=1, completion_tokens=1, total_tokens=2,
        estimated_cost_usd=0.001, duration_sec=0.1, success=True,
    ))
    tracker.reset()
    assert tracker.total_calls == 0
    assert tracker.total_cost_usd == 0.0


def test_cost_tracker_calls_by_model():
    tracker = CostTracker()
    tracker.record(CostEntry(
        ts="", service="s", model="gpt-4", provider="openai",
        prompt_tokens=1, completion_tokens=1, total_tokens=2,
        estimated_cost_usd=0.001, duration_sec=0.1, success=True,
    ))
    tracker.record(CostEntry(
        ts="", service="s", model="claude-3", provider="anthropic",
        prompt_tokens=1, completion_tokens=1, total_tokens=2,
        estimated_cost_usd=0.002, duration_sec=0.1, success=True,
    ))
    tracker.record(CostEntry(
        ts="", service="s", model="gpt-4", provider="openai",
        prompt_tokens=1, completion_tokens=1, total_tokens=2,
        estimated_cost_usd=0.001, duration_sec=0.1, success=True,
    ))
    s = tracker.summary()
    assert s["calls_by_model"] == {"gpt-4": 2, "claude-3": 1}
    assert s["calls_by_service"] == {"s": 3}


def test_get_global_cost_tracker():
    t1 = get_global_cost_tracker()
    t2 = get_global_cost_tracker()
    assert t1 is t2
