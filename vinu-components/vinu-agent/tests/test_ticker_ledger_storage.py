"""Tests for TickerLedgerStore -- Phase 0 foundation plumbing. See
New-talk-agents/new-thinking/new-restructure/phases/phase-0-foundation-plumbing/03-test.md
for the input/expected-output cases this file implements."""

from __future__ import annotations

import re
import tempfile
from pathlib import Path

import pytest

from vinu_agent.storage.ticker_ledger import TickerLedgerStore

_HEX12 = re.compile(r"^[0-9a-f]{12}$")


@pytest.fixture
def store() -> TickerLedgerStore:
    tmp = tempfile.mktemp(suffix=".db")
    s = TickerLedgerStore(tmp)
    yield s
    s.close()
    Path(tmp).unlink(missing_ok=True)


class TestTickerLedgerStore:
    def test_add_event_writes_row(self, store: TickerLedgerStore) -> None:
        event = store.add_event(
            ticker="AAPL",
            stage="summary_agent",
            event_type="summary_refreshed",
            text="refreshed from run_abc123",
            ref_id="run_abc123",
            source="watchlist",
        )
        assert _HEX12.match(event.ledger_id)
        rows = store.get_events("AAPL")
        assert len(rows) == 1
        got = rows[0]
        assert got.ledger_id == event.ledger_id
        assert got.ticker == "AAPL"
        assert got.stage == "summary_agent"
        assert got.event_type == "summary_refreshed"
        assert got.text == "refreshed from run_abc123"
        assert got.ref_id == "run_abc123"
        assert got.source == "watchlist"

    def test_ref_id_and_source_default_to_empty_string(self, store: TickerLedgerStore) -> None:
        event = store.add_event(
            ticker="AAPL",
            stage="summary_agent",
            event_type="summary_refreshed",
            text="...",
        )
        assert event.ref_id == ""
        assert event.source == "watchlist"  # add_event's own default, not blank
        rows = store.get_events("AAPL")
        assert rows[0].ref_id == ""

    def test_events_ordered_chronologically_per_ticker(self, store: TickerLedgerStore) -> None:
        store.add_event(ticker="AAPL", stage="s1", event_type="e1", text="a1")
        store.add_event(ticker="MSFT", stage="s1", event_type="e1", text="m1")
        store.add_event(ticker="AAPL", stage="s2", event_type="e2", text="a2")
        store.add_event(ticker="MSFT", stage="s2", event_type="e2", text="m2")
        store.add_event(ticker="AAPL", stage="s3", event_type="e3", text="a3")

        aapl_events = store.get_events("AAPL")
        assert [e.text for e in aapl_events] == ["a1", "a2", "a3"]
        assert all(e.ticker == "AAPL" for e in aapl_events)

        msft_events = store.get_events("MSFT")
        assert [e.text for e in msft_events] == ["m1", "m2"]

    def test_no_update_or_delete_method_exists(self) -> None:
        assert not hasattr(TickerLedgerStore, "update_event")
        assert not hasattr(TickerLedgerStore, "delete_event")

    def test_ticker_normalized_to_uppercase(self, store: TickerLedgerStore) -> None:
        store.add_event(ticker="aapl", stage="s1", event_type="e1", text="x")
        assert len(store.get_events("AAPL")) == 1
        assert len(store.get_events("aapl")) == 1

    def test_count_events_filters_by_stage_and_event_type(self, store: TickerLedgerStore) -> None:
        store.add_event(ticker="AAPL", stage="risk_gatekeeper", event_type="REJECTED", text="r1")
        store.add_event(ticker="AAPL", stage="risk_gatekeeper", event_type="REJECTED", text="r2")
        store.add_event(ticker="AAPL", stage="risk_gatekeeper", event_type="APPROVED", text="a1")
        store.add_event(ticker="MSFT", stage="risk_gatekeeper", event_type="REJECTED", text="r3")

        assert store.count_events("AAPL", stage="risk_gatekeeper", event_type="REJECTED") == 2
        assert store.count_events("AAPL", stage="risk_gatekeeper") == 3
        assert store.count_events("AAPL") == 3
        assert store.count_events("MSFT", event_type="REJECTED") == 1

    def test_list_events_by_type_spans_every_ticker(self, store: TickerLedgerStore) -> None:
        """Analysis R (25-A-Y-details/05-governance-freshness.md) needs a
        system-wide read that no per-ticker method here provides."""
        store.add_event(ticker="AAPL", stage="planner_triage", event_type="triage_freshness_stale", text="a")
        store.add_event(ticker="MSFT", stage="planner_triage", event_type="triage_freshness_stale", text="b")
        store.add_event(ticker="AAPL", stage="planner_triage", event_type="triage_freshness_fresh", text="c")

        stale = store.list_events_by_type("triage_freshness_stale")
        assert {e.ticker for e in stale} == {"AAPL", "MSFT"}
        assert len(stale) == 2

    def test_list_events_by_type_returns_oldest_first(self, store: TickerLedgerStore) -> None:
        store.add_event(ticker="AAPL", stage="s", event_type="e", text="first")
        store.add_event(ticker="AAPL", stage="s", event_type="e", text="second")
        results = store.list_events_by_type("e")
        assert [e.text for e in results] == ["first", "second"]

    def test_list_events_by_type_unknown_type_returns_empty(self, store: TickerLedgerStore) -> None:
        store.add_event(ticker="AAPL", stage="s", event_type="e1", text="x")
        assert store.list_events_by_type("no-such-type") == []

    def test_list_events_by_types_preserves_true_insertion_order_across_types(
        self, store: TickerLedgerStore,
    ) -> None:
        """The real bug this method exists to prevent: two events of
        different types written in the same second must still come back
        in the order they were actually written, not grouped by type."""
        store.add_event(ticker="AAPL", stage="s", event_type="fresh", text="1st")
        store.add_event(ticker="AAPL", stage="s", event_type="stale", text="2nd")
        store.add_event(ticker="AAPL", stage="s", event_type="fresh", text="3rd")

        results = store.list_events_by_types(["stale", "fresh"])
        assert [e.text for e in results] == ["1st", "2nd", "3rd"]

    def test_list_events_by_types_empty_list_returns_empty(self, store: TickerLedgerStore) -> None:
        store.add_event(ticker="AAPL", stage="s", event_type="e1", text="x")
        assert store.list_events_by_types([]) == []
