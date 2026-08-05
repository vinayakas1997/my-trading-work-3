from pathlib import Path
from tempfile import TemporaryDirectory

from vinu_infra.telemetry import (
    LLMCallRecord,
    StepRecord,
    TelemetryStore,
    get_telemetry_store,
    record_llm_call_safe,
    record_step_safe,
)


def _call(**overrides) -> LLMCallRecord:
    defaults = dict(
        service="vinu-agent",
        model="qwen36-35B",
        base_url="http://host.docker.internal:8009",
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
        token_count_source="provider",
        retry_count=0,
        latency_sec=1.5,
        success=True,
        outcome="completed",
    )
    defaults.update(overrides)
    return LLMCallRecord(**defaults)


def _step(**overrides) -> StepRecord:
    defaults = dict(
        service="vinu-agent",
        step_name="get_fundamentals",
        duration_sec=0.4,
        success=True,
        outcome="completed",
    )
    defaults.update(overrides)
    return StepRecord(**defaults)


def test_record_and_read_llm_call():
    with TemporaryDirectory() as tmp:
        store = TelemetryStore(Path(tmp) / "telemetry.db")
        store.record_llm_call(_call())
        rows = store.recent_llm_calls()
        assert len(rows) == 1
        assert rows[0]["prompt_tokens"] == 100
        assert rows[0]["token_count_source"] == "provider"
        assert rows[0]["success"] == 1
        store.close()


def test_record_and_read_step():
    with TemporaryDirectory() as tmp:
        store = TelemetryStore(Path(tmp) / "telemetry.db")
        store.record_step(_step(outcome="tool_error", success=False, error="timeout"))
        rows = store.recent_steps()
        assert len(rows) == 1
        assert rows[0]["outcome"] == "tool_error"
        assert rows[0]["success"] == 0
        assert rows[0]["error"] == "timeout"
        store.close()


def test_recent_llm_calls_filters_by_service():
    with TemporaryDirectory() as tmp:
        store = TelemetryStore(Path(tmp) / "telemetry.db")
        store.record_llm_call(_call(service="vinu-agent"))
        store.record_llm_call(_call(service="vinu-research"))
        agent_rows = store.recent_llm_calls(service="vinu-agent")
        assert len(agent_rows) == 1
        assert agent_rows[0]["service"] == "vinu-agent"
        store.close()


def test_recent_llm_calls_ordered_newest_first():
    with TemporaryDirectory() as tmp:
        store = TelemetryStore(Path(tmp) / "telemetry.db")
        store.record_llm_call(_call(model="model-1"))
        store.record_llm_call(_call(model="model-2"))
        rows = store.recent_llm_calls()
        assert rows[0]["model"] == "model-2"
        assert rows[1]["model"] == "model-1"
        store.close()


def test_summary_aggregates_calls_and_retries():
    with TemporaryDirectory() as tmp:
        store = TelemetryStore(Path(tmp) / "telemetry.db")
        store.record_llm_call(_call(total_tokens=100, retry_count=1, success=True))
        store.record_llm_call(_call(total_tokens=200, retry_count=2, success=False, outcome="error"))
        summary = store.summary()
        assert summary["llm_calls"]["n"] == 2
        assert summary["llm_calls"]["tokens"] == 300
        assert summary["llm_calls"]["retries"] == 3
        assert summary["llm_calls"]["failures"] == 1
        store.close()


def test_summary_groups_steps_by_outcome():
    with TemporaryDirectory() as tmp:
        store = TelemetryStore(Path(tmp) / "telemetry.db")
        store.record_step(_step(outcome="completed"))
        store.record_step(_step(outcome="completed"))
        store.record_step(_step(outcome="tool_error", success=False))
        summary = store.summary()
        assert summary["steps_by_outcome"]["completed"] == 2
        assert summary["steps_by_outcome"]["tool_error"] == 1
        store.close()


def test_get_telemetry_store_returns_same_instance_for_same_path():
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "telemetry.db"
        store1 = get_telemetry_store(path)
        store2 = get_telemetry_store(path)
        assert store1 is store2
        store1.close()


def test_get_telemetry_store_returns_different_instances_for_different_paths():
    with TemporaryDirectory() as tmp:
        store1 = get_telemetry_store(Path(tmp) / "a.db")
        store2 = get_telemetry_store(Path(tmp) / "b.db")
        assert store1 is not store2
        store1.close()
        store2.close()


def test_record_llm_call_safe_writes_via_global_cache():
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "telemetry.db"
        record_llm_call_safe(_call(), db_path=path)
        rows = get_telemetry_store(path).recent_llm_calls()
        assert len(rows) == 1
        get_telemetry_store(path).close()


def test_record_step_safe_never_raises_on_bad_path():
    # A path under a nonexistent, unwritable root should be swallowed, not
    # propagate — telemetry must never break the caller's real request path.
    record_step_safe(_step(), db_path="/nonexistent-root-xyz/telemetry.db")
