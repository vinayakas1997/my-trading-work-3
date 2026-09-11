"""Stage C (C7): per-instrument trade-limit *value* storage — the other
half of C7, complementing C4's coarse-state `symbol_overrides.py`."""

from __future__ import annotations

import pytest

from vinu_agent.broker.symbol_limits import SymbolLimitStore


@pytest.fixture
def store():
    return SymbolLimitStore(":memory:")


class TestSetGet:
    def test_set_get_roundtrip_uppercases_symbol(self, store) -> None:
        store.set("aapl", max_order_value=500.0, reason="volatile small-cap", set_by="ops")
        rec = store.get("AAPL")
        assert rec is not None
        assert rec.symbol == "AAPL"
        assert rec.max_order_value == 500.0
        assert rec.max_position_pct is None
        assert rec.reason == "volatile small-cap"
        assert rec.set_by == "ops"

    def test_get_unknown_symbol_is_none(self, store) -> None:
        assert store.get("GHOST") is None

    def test_all_returns_every_symbol_sorted(self, store) -> None:
        store.set("MSFT", max_order_value=1.0)
        store.set("AAPL", max_order_value=2.0)
        assert [r.symbol for r in store.all()] == ["AAPL", "MSFT"]


class TestMergeSemantics:
    def test_second_set_only_touches_the_fields_it_passes(self, store) -> None:
        store.set("AAPL", max_order_value=500.0, max_position_pct=0.1)
        store.set("AAPL", max_position_pct=0.2)  # max_order_value not passed
        rec = store.get("AAPL")
        assert rec.max_order_value == 500.0  # untouched
        assert rec.max_position_pct == 0.2

    def test_none_default_never_overwrites_an_existing_value(self, store) -> None:
        store.set("AAPL", max_order_value=500.0)
        store.set("AAPL", max_capital_utilization_pct=0.5)
        assert store.get("AAPL").max_order_value == 500.0


class TestClearing:
    def test_clear_is_independent_per_symbol(self, store) -> None:
        store.set("AAPL", max_order_value=1.0)
        store.set("MSFT", max_order_value=2.0)
        assert store.clear("AAPL") is True
        assert store.get("AAPL") is None
        assert store.get("MSFT") is not None
        assert store.clear("AAPL") is False

    def test_clear_field_nulls_only_that_field(self, store) -> None:
        store.set("AAPL", max_order_value=500.0, max_position_pct=0.1)
        store.clear_field("AAPL", "max_order_value")
        rec = store.get("AAPL")
        assert rec.max_order_value is None
        assert rec.max_position_pct == 0.1

    def test_clear_field_on_unset_symbol_is_a_noop(self, store) -> None:
        assert store.clear_field("GHOST", "max_order_value") is None

    def test_clear_field_rejects_unknown_field(self, store) -> None:
        store.set("AAPL", max_order_value=1.0)
        with pytest.raises(ValueError):
            store.clear_field("AAPL", "not_a_real_field")


class TestHistory:
    def test_set_records_a_history_entry_for_a_changed_field(self, store) -> None:
        store.set("AAPL", max_order_value=1000.0)
        store.set("AAPL", max_order_value=500.0)
        history = store.history("AAPL")
        assert len(history) == 2
        assert history[0].old_value == 1000.0
        assert history[0].new_value == 500.0

    def test_set_with_same_value_does_not_add_a_duplicate_history_row(self, store) -> None:
        store.set("AAPL", max_order_value=500.0)
        store.set("AAPL", max_order_value=500.0)  # unchanged
        assert len(store.history("AAPL")) == 1

    def test_untouched_field_produces_no_history_row(self, store) -> None:
        store.set("AAPL", max_order_value=500.0, max_position_pct=0.1)
        before = len(store.history("AAPL"))
        store.set("AAPL", max_position_pct=0.2)
        history = store.history("AAPL")
        assert len(history) == before + 1  # only the touched field added a row
        assert history[0].field == "max_position_pct"

    def test_clear_field_is_recorded_with_null_new_value(self, store) -> None:
        store.set("AAPL", max_order_value=500.0)
        store.clear_field("AAPL", "max_order_value")
        history = store.history("AAPL")
        assert history[0].new_value is None
        assert history[0].old_value == 500.0

    def test_history_without_symbol_spans_all_symbols(self, store) -> None:
        store.set("AAPL", max_order_value=1.0)
        store.set("MSFT", max_order_value=2.0)
        assert len(store.history()) == 2

    def test_history_limit_caps_results(self, store) -> None:
        for i in range(5):
            store.set("AAPL", max_order_value=float(i))
        assert len(store.history("AAPL", limit=2)) == 2

    def test_history_survives_clear(self, store) -> None:
        store.set("AAPL", max_order_value=500.0)
        store.clear("AAPL")
        assert len(store.history("AAPL")) == 1  # the original set() is still on record
