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
