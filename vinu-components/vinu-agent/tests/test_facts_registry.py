"""Tests for the Facts & Limitations Registry (vinu_agent/facts/)."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from vinu_agent.facts.registry import Fact, FactsRegistry
from vinu_agent.facts.seed import SEED_FACTS, seed_if_empty


@pytest.fixture
def registry() -> FactsRegistry:
    tmp = tempfile.mktemp(suffix=".db")
    r = FactsRegistry(tmp)
    yield r
    r.close()
    Path(tmp).unlink(missing_ok=True)


def test_add_fact_rejects_invalid_kind(registry: FactsRegistry):
    with pytest.raises(ValueError):
        registry.add_fact(Fact(id="", statement="x", kind="maybe"))


def test_add_and_fetch_symbol_scoped_fact(registry: FactsRegistry):
    registry.add_fact(
        Fact(id="", statement="JNJ price was fabricated once", kind="known-bug", symbols=["JNJ"])
    )
    facts = registry.active_facts_for(symbols=["JNJ"])
    assert len(facts) == 1
    assert facts[0].statement == "JNJ price was fabricated once"

    assert registry.active_facts_for(symbols=["AAPL"]) == []


def test_unscoped_fact_applies_universally(registry: FactsRegistry):
    registry.add_fact(Fact(id="", statement="silence isn't safety", kind="known-bug"))
    assert len(registry.active_facts_for(symbols=["AAPL"])) == 1
    assert len(registry.active_facts_for(symbols=["TSLA"])) == 1
    assert len(registry.active_facts_for()) == 1


def test_signal_scoped_fact_matches_by_signal(registry: FactsRegistry):
    registry.add_fact(
        Fact(
            id="", statement="direction prediction is a coin flip", kind="disproven",
            signals=["significance_score"],
        )
    )
    assert len(registry.active_facts_for(signals=["significance_score"])) == 1
    assert registry.active_facts_for(signals=["other_signal"]) == []


def test_supersede_removes_fact_from_active_results(registry: FactsRegistry):
    fid = registry.add_fact(Fact(id="", statement="temp fact", kind="proven", symbols=["MSFT"]))
    registry.supersede(fid)
    assert registry.active_facts_for(symbols=["MSFT"]) == []


def test_seed_if_empty_inserts_all_seed_facts_once(registry: FactsRegistry):
    inserted = seed_if_empty(registry)
    assert inserted == len(SEED_FACTS)
    assert registry.count_active() == len(SEED_FACTS)

    inserted_again = seed_if_empty(registry)
    assert inserted_again == 0
    assert registry.count_active() == len(SEED_FACTS)


def test_seeded_jnj_fact_is_retrievable_by_symbol(registry: FactsRegistry):
    seed_if_empty(registry)
    facts = registry.active_facts_for(symbols=["JNJ"])
    assert any("fabricated" in f.statement for f in facts)
