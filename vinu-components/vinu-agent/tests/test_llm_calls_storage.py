"""Tests for the every-LLM-call log (prompt/response/tokens/latency)."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from vinu_agent.storage.llm_calls import LlmCallLogStore, LlmCallRecord


@pytest.fixture
def store() -> LlmCallLogStore:
    tmp = tempfile.mktemp(suffix=".db")
    s = LlmCallLogStore(tmp)
    yield s
    s.close()
    Path(tmp).unlink(missing_ok=True)


def _make_record(**overrides) -> LlmCallRecord:
    defaults = dict(
        service="vinu-agent",
        tier="specialist",
        team="research",
        agent="idea_generator",
        role="idea-generator",
        session_id="sess-1",
        provider="OpenAIChatLLM",
        model="gpt-4o",
        base_url="https://api.openai.com/v1",
        prompt=[{"role": "system", "content": "You are..."}, {"role": "user", "content": "Do X"}],
        tools=[{"type": "function", "function": {"name": "echo"}}],
        response_content="Here is the answer.",
        response_tool_calls=[],
        prompt_tokens=120,
        completion_tokens=40,
        total_tokens=160,
        token_count_source="provider",
        retry_count=0,
        latency_sec=1.25,
        success=True,
        error="",
    )
    defaults.update(overrides)
    return LlmCallRecord(**defaults)


class TestLlmCallLogStore:
    def test_record_and_get_round_trips_every_field(self, store: LlmCallLogStore) -> None:
        record = _make_record()
        store.record(record)
        fetched = store.get_call(record.call_id)
        assert fetched is not None
        assert fetched.service == "vinu-agent"
        assert fetched.tier == "specialist"
        assert fetched.team == "research"
        assert fetched.agent == "idea_generator"
        assert fetched.role == "idea-generator"
        assert fetched.session_id == "sess-1"
        assert fetched.provider == "OpenAIChatLLM"
        assert fetched.model == "gpt-4o"
        assert fetched.base_url == "https://api.openai.com/v1"
        assert fetched.prompt == record.prompt
        assert fetched.tools == record.tools
        assert fetched.response_content == "Here is the answer."
        assert fetched.prompt_tokens == 120
        assert fetched.completion_tokens == 40
        assert fetched.total_tokens == 160
        assert fetched.token_count_source == "provider"
        assert fetched.latency_sec == 1.25
        assert fetched.success is True

    def test_records_failure_with_error_message(self, store: LlmCallLogStore) -> None:
        record = _make_record(success=False, error="connection refused", response_content="")
        store.record(record)
        fetched = store.get_call(record.call_id)
        assert fetched.success is False
        assert fetched.error == "connection refused"

    def test_get_call_returns_none_for_unknown_id(self, store: LlmCallLogStore) -> None:
        assert store.get_call("nope") is None

    def test_list_calls_orders_newest_first(self, store: LlmCallLogStore) -> None:
        r1 = _make_record()
        r2 = _make_record()
        store.record(r1)
        store.record(r2)
        calls = store.list_calls()
        assert len(calls) == 2

    def test_list_calls_filters_by_tier(self, store: LlmCallLogStore) -> None:
        store.record(_make_record(tier="orchestrator", agent="manager"))
        store.record(_make_record(tier="specialist"))
        orchestrator_calls = store.list_calls(tier="orchestrator")
        assert len(orchestrator_calls) == 1
        assert orchestrator_calls[0].tier == "orchestrator"

    def test_list_calls_filters_by_team(self, store: LlmCallLogStore) -> None:
        store.record(_make_record(team="research"))
        store.record(_make_record(team="enhancer"))
        research_calls = store.list_calls(team="research")
        assert len(research_calls) == 1
        assert research_calls[0].team == "research"

    def test_list_calls_filters_by_session_id(self, store: LlmCallLogStore) -> None:
        store.record(_make_record(session_id="sess-a"))
        store.record(_make_record(session_id="sess-b"))
        calls = store.list_calls(session_id="sess-a")
        assert len(calls) == 1
        assert calls[0].session_id == "sess-a"

    def test_total_tokens_by_tier_aggregates_correctly(self, store: LlmCallLogStore) -> None:
        store.record(_make_record(tier="orchestrator", total_tokens=100))
        store.record(_make_record(tier="orchestrator", total_tokens=50))
        store.record(_make_record(tier="specialist", total_tokens=200))
        totals = store.total_tokens_by_tier()
        assert totals["orchestrator"] == 150
        assert totals["specialist"] == 200
