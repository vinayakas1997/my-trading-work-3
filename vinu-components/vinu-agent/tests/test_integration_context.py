"""Integration test: ContextBuilder + UnifiedMemoryStore.

Verifies that real memory entries flow through to the agent context
with scored search, dedup, and token-budget enforcement.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from vinu_agent.agent.context import ContextBuilder
from vinu_agent.agent.tools import ToolRegistry
from vinu_agent.memory.unified_store import MemoryEntry, UnifiedMemoryStore, _now


@pytest.fixture
def store() -> UnifiedMemoryStore:
    tmp = tempfile.mktemp(suffix=".db")
    s = UnifiedMemoryStore(tmp)
    yield s
    s.close()
    Path(tmp).unlink(missing_ok=True)


@pytest.fixture
def builder(store: UnifiedMemoryStore) -> ContextBuilder:
    registry = ToolRegistry()
    return ContextBuilder(
        registry=registry,
        unified_memory=store,
    )


def _make_memory(source: str, symbol: str, title: str, content: str, memory_type: str = "note") -> MemoryEntry:
    return MemoryEntry(
        id=f"{source}-{symbol}-test",
        source=source,
        source_id=f"{source}-{symbol}-uid",
        symbol=symbol,
        memory_type=memory_type,
        title=title,
        content=content,
        summary=content[:100],
        score=0.0,
        created_at=_now(),
        updated_at=_now(),
    )


class TestContextMemoryIntegration:
    def test_memory_appears_in_context(self, store: UnifiedMemoryStore, builder: ContextBuilder) -> None:
        store.add_entry(_make_memory("research", "AAPL", "Strong trend", "AAPL has strong upward momentum"))
        store.add_entry(_make_memory("news", "AAPL", "Earnings beat", "AAPL earnings exceeded expectations"))

        messages = builder.build_messages([], "What is the outlook for AAPL?")
        user_content = messages[-1]["content"]
        assert "<memory symbol=AAPL>" in user_content
        assert "Strong trend" in user_content
        assert "Earnings beat" in user_content

    def test_no_memory_for_unmentioned_symbol(self, store: UnifiedMemoryStore, builder: ContextBuilder) -> None:
        store.add_entry(_make_memory("research", "AAPL", "Strong trend", "content"))
        messages = builder.build_messages([], "What about TSLA?")
        user_content = messages[-1]["content"]
        assert "<memory symbol=AAPL>" not in user_content
        assert "<memory symbol=TSLA>" not in user_content

    def test_dedup_prevents_duplicate_source_id(self, store: UnifiedMemoryStore, builder: ContextBuilder) -> None:
        same_id = "dup-research-id"
        store.add_entry(MemoryEntry(
            id="entry-1", source="research", source_id=same_id,
            symbol="AAPL", title="First", content="a", summary="a",
            created_at=_now(), updated_at=_now(),
        ))
        store.add_entry(MemoryEntry(
            id="entry-2", source="research", source_id=same_id,
            symbol="AAPL", title="Second (dup)", content="b", summary="b",
            created_at=_now(), updated_at=_now(),
        ))
        messages = builder.build_messages([], "Check AAPL")
        content = messages[-1]["content"]
        assert "First" in content
        assert "Second (dup)" not in content

    def test_token_budget_truncates_low_priority(self, store: UnifiedMemoryStore) -> None:
        registry = ToolRegistry()
        builder = ContextBuilder(registry=registry, unified_memory=store, max_memory_tokens=50)
        for i in range(5):
            store.add_entry(_make_memory("research", "AAPL", f"Entry {i}", "x " * 30))
        messages = builder.build_messages([], "Analyze AAPL please")
        content = messages[-1]["content"]
        memory_blocks = content.count("<memory symbol=AAPL>")
        assert memory_blocks <= 1, "budget should limit to at most one block"
