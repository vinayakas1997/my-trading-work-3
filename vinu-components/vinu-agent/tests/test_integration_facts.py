"""Integration test: ContextBuilder + FactsRegistry.

Named acceptance test from implementation-plan-from-04/AGENTS.md: confirm a
seeded row actually appears in the injected context block for a matching
symbol/signal — not just that the row exists in the store. A row that exists
in the database but never reaches the model is functionally identical to it
not existing at all.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from vinu_agent.agent.context import ContextBuilder
from vinu_agent.agent.tools import ToolRegistry
from vinu_agent.facts.registry import Fact, FactsRegistry


@pytest.fixture
def registry() -> FactsRegistry:
    tmp = tempfile.mktemp(suffix=".db")
    r = FactsRegistry(tmp)
    yield r
    r.close()
    Path(tmp).unlink(missing_ok=True)


@pytest.fixture
def builder(registry: FactsRegistry) -> ContextBuilder:
    return ContextBuilder(registry=ToolRegistry(), facts_registry=registry)


def test_symbol_matching_fact_reaches_injected_block(registry: FactsRegistry, builder: ContextBuilder):
    registry.add_fact(
        Fact(id="", statement="JNJ price was fabricated once", kind="known-bug", symbols=["JNJ"])
    )
    messages = builder.build_messages([], "What's happening with JNJ today?")
    known_constraints = [m for m in messages if ContextBuilder.is_known_constraints_msg(m)]
    assert len(known_constraints) == 1
    assert "JNJ price was fabricated once" in known_constraints[0]["content"]
    assert builder.last_facts_msg is not None


def test_fact_for_unmentioned_symbol_does_not_leak_in(registry: FactsRegistry, builder: ContextBuilder):
    registry.add_fact(
        Fact(id="", statement="MSFT-only fact", kind="proven", symbols=["MSFT"])
    )
    messages = builder.build_messages([], "What's happening with JNJ today?")
    known_constraints = [m for m in messages if ContextBuilder.is_known_constraints_msg(m)]
    assert known_constraints == []
    assert builder.last_facts_msg is None


def test_held_symbol_fact_reaches_context_even_without_mention(registry: FactsRegistry):
    registry.add_fact(
        Fact(id="", statement="held-position fact", kind="known-bug", symbols=["TSLA"])
    )
    builder = ContextBuilder(registry=ToolRegistry(), facts_registry=registry, held_symbols=["TSLA"])
    messages = builder.build_messages([], "General market check-in, no tickers mentioned")
    known_constraints = [m for m in messages if ContextBuilder.is_known_constraints_msg(m)]
    assert len(known_constraints) == 1
    assert "held-position fact" in known_constraints[0]["content"]


def test_unscoped_fact_always_reaches_context(registry: FactsRegistry, builder: ContextBuilder):
    registry.add_fact(Fact(id="", statement="global constraint", kind="known-bug"))
    messages = builder.build_messages([], "Anything, no symbols here")
    known_constraints = [m for m in messages if ContextBuilder.is_known_constraints_msg(m)]
    assert len(known_constraints) == 1
    assert "global constraint" in known_constraints[0]["content"]


def test_no_facts_registry_means_no_block_and_no_crash():
    builder = ContextBuilder(registry=ToolRegistry())
    messages = builder.build_messages([], "JNJ check")
    assert not any(ContextBuilder.is_known_constraints_msg(m) for m in messages)
    assert builder.last_facts_msg is None
