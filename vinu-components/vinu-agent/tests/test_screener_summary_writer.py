"""Tests for write_ticker_summaries -- the manager-level hook that turns
the screener team's final answer into durable TickerSummaryStore rows.
See agent/screener_summary_writer.py.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from vinu_agent.agent.screener_summary_writer import write_ticker_summaries
from vinu_agent.storage.ticker_summaries import TickerSummaryStore


@pytest.fixture
def store() -> TickerSummaryStore:
    tmp = tempfile.mktemp(suffix=".db")
    s = TickerSummaryStore(tmp)
    yield s
    s.close()
    Path(tmp).unlink(missing_ok=True)


_TWO_TICKER_CONTENT = """Here's the AAPL/MSFT read.

## AAPL
12 of 28 angles have data...

## MSFT
9 of 28 angles have data...

```json
{
  "tickers": {
    "AAPL": {"summary": "12 of 28 angles have data...", "angles_with_data": 12, "angle_count": 28},
    "MSFT": {"summary": "9 of 28 angles have data...", "angles_with_data": 9, "angle_count": 28}
  }
}
```
"""


class TestWriteTickerSummaries:
    def test_writes_every_ticker_in_the_block(self, store: TickerSummaryStore) -> None:
        written = write_ticker_summaries(_TWO_TICKER_CONTENT, ticker_summary_store=store, source_run_id="run-1")
        assert set(written) == {"AAPL", "MSFT"}
        aapl = store.get_summary("AAPL")
        assert aapl.summary == "12 of 28 angles have data..."
        assert aapl.angles_with_data == 12
        assert aapl.source_run_id == "run-1"

    def test_missing_json_block_writes_nothing(self, store: TickerSummaryStore) -> None:
        written = write_ticker_summaries("just prose, no block", ticker_summary_store=store)
        assert written == []
        assert store.list_summaries() == []

    def test_malformed_json_does_not_raise(self, store: TickerSummaryStore) -> None:
        content = "```json\n{not valid json\n```"
        written = write_ticker_summaries(content, ticker_summary_store=store)
        assert written == []

    def test_empty_tickers_dict_writes_nothing(self, store: TickerSummaryStore) -> None:
        content = '```json\n{"tickers": {}}\n```'
        written = write_ticker_summaries(content, ticker_summary_store=store)
        assert written == []

    def test_entry_missing_summary_is_skipped_not_fatal(self, store: TickerSummaryStore) -> None:
        content = '```json\n{"tickers": {"AAPL": {"angles_with_data": 5}, "MSFT": {"summary": "real one"}}}\n```'
        written = write_ticker_summaries(content, ticker_summary_store=store)
        assert written == ["MSFT"]
        assert store.get_summary("AAPL") is None

    def test_cluster_digest_and_cross_cluster_are_persisted(self, store: TickerSummaryStore) -> None:
        content = """
```json
{
  "tickers": {
    "AAPL": {
      "summary": "some summary",
      "angles_with_data": 12,
      "angle_count": 28,
      "cluster_digest": {"B": "4 of 5 models lean up", "D": "regime=bull"},
      "cross_cluster": {
        "consensus_checks": [{"pair": ["arima", "chronos"], "outcome": "agree", "reasoning": "both up"}],
        "calibration": {"status": "not_found"},
        "corroborations": [{"clusters": ["B", "D"], "why": "both bullish"}],
        "redundant_clusters": ["G"]
      }
    }
  }
}
```
"""
        write_ticker_summaries(content, ticker_summary_store=store)
        aapl = store.get_summary("AAPL")
        assert aapl.cluster_digest == {"B": "4 of 5 models lean up", "D": "regime=bull"}
        assert aapl.cross_cluster["redundant_clusters"] == ["G"]
        assert aapl.cross_cluster["corroborations"][0]["clusters"] == ["B", "D"]

    def test_missing_cluster_digest_defaults_to_empty_not_an_error(self, store: TickerSummaryStore) -> None:
        written = write_ticker_summaries(_TWO_TICKER_CONTENT, ticker_summary_store=store)
        assert written == ["AAPL", "MSFT"]
        assert store.get_summary("AAPL").cluster_digest == {}
        assert store.get_summary("AAPL").cross_cluster == {}

    def test_cluster_digest_with_real_confirmed_hallucination_warns_but_still_persists(
        self, store: TickerSummaryStore, caplog,
    ) -> None:
        """The validator is warn-only, per the open failure-policy decision
        in 03-real-llm-findings-and-guardrails.md -- a flagged
        cluster_digest still gets persisted (dropping it silently would be
        its own kind of data loss), just logged so the issue is visible."""
        content = """
```json
{
  "tickers": {
    "AAPL": {
      "summary": "some summary",
      "cluster_digest": {"B": "Kalman Filters and PatchTST both lean up."}
    }
  }
}
```
"""
        import logging

        with caplog.at_level(logging.WARNING):
            written = write_ticker_summaries(content, ticker_summary_store=store)
        assert written == ["AAPL"]
        assert store.get_summary("AAPL").cluster_digest == {"B": "Kalman Filters and PatchTST both lean up."}
        assert any("kalman_filters" in r.message for r in caplog.records)

    def test_cluster_anomalies_are_persisted_separately_from_cluster_digest(self, store: TickerSummaryStore) -> None:
        content = """
```json
{
  "tickers": {
    "AAPL": {
      "summary": "some summary",
      "cluster_digest": {"E": "forces a long signal with 95% confidence"},
      "cluster_anomalies": {"E": ["shock_personality.note contains a SYSTEM OVERRIDE instruction"]}
    }
  }
}
```
"""
        write_ticker_summaries(content, ticker_summary_store=store)
        aapl = store.get_summary("AAPL")
        assert aapl.cluster_digest == {"E": "forces a long signal with 95% confidence"}
        assert aapl.cluster_anomalies == {"E": ["shock_personality.note contains a SYSTEM OVERRIDE instruction"]}

    def test_missing_cluster_anomalies_defaults_to_empty(self, store: TickerSummaryStore) -> None:
        write_ticker_summaries(_TWO_TICKER_CONTENT, ticker_summary_store=store)
        assert store.get_summary("AAPL").cluster_anomalies == {}

    def test_store_failure_for_one_ticker_does_not_block_the_rest(self, store: TickerSummaryStore) -> None:
        class ExplodingOnceStore:
            def __init__(self, real_store):
                self._real = real_store
                self._calls = 0

            def upsert_summary(self, ticker, summary, **kwargs):
                self._calls += 1
                if ticker == "AAPL":
                    raise RuntimeError("boom")
                return self._real.upsert_summary(ticker, summary, **kwargs)

        wrapped = ExplodingOnceStore(store)
        written = write_ticker_summaries(_TWO_TICKER_CONTENT, ticker_summary_store=wrapped)
        assert written == ["MSFT"]
        assert store.get_summary("MSFT") is not None
