"""Tests for TickerSummaryStore -- the durable output of the screener
team's per-ticker angle synthesis. See storage/ticker_summaries.py."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from vinu_agent.storage.ticker_summaries import TickerSummaryStore


@pytest.fixture
def store() -> TickerSummaryStore:
    tmp = tempfile.mktemp(suffix=".db")
    s = TickerSummaryStore(tmp)
    yield s
    s.close()
    Path(tmp).unlink(missing_ok=True)


class TestTickerSummaryStore:
    def test_upsert_then_get(self, store: TickerSummaryStore) -> None:
        store.upsert_summary("AAPL", "12 of 28 angles have data...", angles_with_data=12, angle_count=28, source_run_id="run-1")
        fetched = store.get_summary("AAPL")
        assert fetched is not None
        assert fetched.summary == "12 of 28 angles have data..."
        assert fetched.angles_with_data == 12
        assert fetched.angle_count == 28
        assert fetched.source_run_id == "run-1"

    def test_ticker_normalized_to_uppercase(self, store: TickerSummaryStore) -> None:
        store.upsert_summary("aapl", "summary text")
        assert store.get_summary("AAPL") is not None
        assert store.get_summary("aapl") is not None

    def test_get_unknown_ticker_returns_none(self, store: TickerSummaryStore) -> None:
        assert store.get_summary("NOPE") is None

    def test_upsert_overwrites_not_versions(self, store: TickerSummaryStore) -> None:
        """One row per ticker, the latest read -- not a history."""
        store.upsert_summary("AAPL", "first summary", angles_with_data=5)
        store.upsert_summary("AAPL", "second summary", angles_with_data=10)
        fetched = store.get_summary("AAPL")
        assert fetched.summary == "second summary"
        assert fetched.angles_with_data == 10
        assert len(store.list_summaries()) == 1

    def test_created_at_preserved_across_updates(self, store: TickerSummaryStore) -> None:
        first = store.upsert_summary("AAPL", "v1")
        second = store.upsert_summary("AAPL", "v2")
        assert second.created_at == first.created_at
        assert second.updated_at >= first.updated_at

    def test_list_summaries_returns_all(self, store: TickerSummaryStore) -> None:
        store.upsert_summary("AAPL", "a")
        store.upsert_summary("MSFT", "m")
        tickers = {s.ticker for s in store.list_summaries()}
        assert tickers == {"AAPL", "MSFT"}

    def test_record_gate_check_on_existing_row_does_not_touch_summary(
        self, store: TickerSummaryStore
    ) -> None:
        store.upsert_summary("AAPL", "real summary", source_run_id="run-1")
        store.record_gate_check("AAPL", run_id="run-1", artifact_signature="sig-a")
        fetched = store.get_summary("AAPL")
        assert fetched.summary == "real summary"
        assert fetched.source_run_id == "run-1"
        assert fetched.last_checked_run_id == "run-1"
        assert fetched.last_checked_artifact_signature == "sig-a"

    def test_record_gate_check_on_ticker_with_no_summary_yet(
        self, store: TickerSummaryStore
    ) -> None:
        store.record_gate_check("AAPL", run_id="run-1", artifact_signature="sig-a")
        fetched = store.get_summary("AAPL")
        assert fetched is not None
        assert fetched.summary == ""
        assert fetched.last_checked_run_id == "run-1"
        assert fetched.last_checked_artifact_signature == "sig-a"

    def test_record_gate_check_updates_on_repeat_call(
        self, store: TickerSummaryStore
    ) -> None:
        store.record_gate_check("AAPL", run_id="run-1", artifact_signature="sig-a")
        store.record_gate_check("AAPL", run_id="run-2", artifact_signature="sig-b")
        fetched = store.get_summary("AAPL")
        assert fetched.last_checked_run_id == "run-2"
        assert fetched.last_checked_artifact_signature == "sig-b"
