"""Stage C (C4/C7): the per-symbol override store."""

from __future__ import annotations

import pytest

from vinu_agent.broker.guard_codes import OverrideState
from vinu_agent.broker.symbol_overrides import (
    InvalidOverrideTransition,
    SymbolOverrideStore,
)


@pytest.fixture
def store():
    return SymbolOverrideStore(":memory:")


def test_set_get_roundtrip_uppercases_symbol(store) -> None:
    store.set("aapl", OverrideState.UNTRADEABLE, reason="halted news", set_by="ops")
    rec = store.get("AAPL")
    assert rec is not None
    assert rec.symbol == "AAPL"
    assert rec.state is OverrideState.UNTRADEABLE
    assert rec.reason == "halted news"
    assert rec.set_by == "ops"
    assert rec.set_at > 0


def test_get_unknown_symbol_is_none(store) -> None:
    assert store.get("MSFT") is None


def test_clear_is_independent_per_symbol(store) -> None:
    store.set("AAPL", OverrideState.UNTRADEABLE)
    store.set("MSFT", OverrideState.REDUCE_ONLY)
    assert store.clear("AAPL") is True
    assert store.get("AAPL") is None
    assert store.get("MSFT") is not None       # untouched
    assert store.clear("AAPL") is False        # already gone


def test_all_lists_every_override_sorted(store) -> None:
    store.set("MSFT", OverrideState.REDUCE_ONLY)
    store.set("AAPL", OverrideState.UNTRADEABLE)
    assert [r.symbol for r in store.all()] == ["AAPL", "MSFT"]


def test_disallowed_transition_is_refused(store) -> None:
    store.set("AAPL", OverrideState.IGNORED)
    # IGNORED -> REDUCE_ONLY is allowed; IGNORED -> IGNORED is a no-op (allowed);
    # but a bogus jump is refused. REDUCE_ONLY -> IGNORED is allowed, so pick a
    # genuinely disallowed one: there is none from IGNORED in this map besides
    # the two listed, so verify the map is actually enforced via a fresh symbol.
    store.set("MSFT", OverrideState.REDUCE_ONLY)
    store.set("MSFT", OverrideState.UNTRADEABLE)  # allowed
    # now UNTRADEABLE -> REDUCE_ONLY allowed, UNTRADEABLE -> UNTRADEABLE no-op...
    # force a refusal by monkeypatching is overkill; instead assert the guard
    # rejects an unknown target type
    with pytest.raises(InvalidOverrideTransition):
        # simulate a stale client: pretend current is IGNORED and target is a
        # state not reachable from it -- there is none in the default map, so
        # this test instead checks the happy path is enforced by transitions.
        _force_invalid(store)


def _force_invalid(store) -> None:
    # AAPL is IGNORED; ALLOWED_OVERRIDE_TRANSITIONS[IGNORED] =
    # {UNTRADEABLE, REDUCE_ONLY}. Temporarily shrink it so a transition that
    # would normally pass is now refused, proving set() actually consults it.
    import vinu_agent.broker.guard_codes as gc

    original = gc.ALLOWED_OVERRIDE_TRANSITIONS[OverrideState.IGNORED]
    gc.ALLOWED_OVERRIDE_TRANSITIONS[OverrideState.IGNORED] = set()
    try:
        store.set("AAPL", OverrideState.UNTRADEABLE)
    finally:
        gc.ALLOWED_OVERRIDE_TRANSITIONS[OverrideState.IGNORED] = original


def test_clearing_then_resetting_is_always_allowed(store) -> None:
    store.set("AAPL", OverrideState.UNTRADEABLE)
    store.clear("AAPL")
    # from no-override, any state is reachable again
    store.set("AAPL", OverrideState.IGNORED)
    assert store.get("AAPL").state is OverrideState.IGNORED
