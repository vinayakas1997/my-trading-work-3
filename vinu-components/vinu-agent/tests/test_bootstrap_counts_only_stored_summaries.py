"""A finished screener run is not a stored summary. The TSLA bootstrap finished with a full analysis but no JSON block
(the cross-cluster analyst timed out), nothing was stored, nothing was logged, and the planner reported it as
"bootstrapped". Only a ticker with a row in the store may count, and the miss must be logged."""

from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import patch

from vinu_agent.agent import scheduler_workers
from vinu_agent.agent.screener_summary_writer import write_ticker_summaries


class _Store:
    def __init__(self, rows=()):
        self.rows = {r: SimpleNamespace(ticker=r) for r in rows}

    def list_summaries(self):
        return list(self.rows.values())

    def get_summary(self, ticker):
        return self.rows.get(ticker)

    def upsert_summary(self, ticker, *a, **k):
        self.rows[ticker] = SimpleNamespace(ticker=ticker)


def _service(store):
    return SimpleNamespace(ticker_summary_store=store, config=SimpleNamespace(summary_parallelism=1))


def test_a_run_that_stores_nothing_is_not_counted_and_is_logged(caplog):
    store = _Store()
    with patch.object(scheduler_workers, "run_team_for_ticker", lambda *a, **k: None), caplog.at_level(logging.WARNING):
        done = scheduler_workers.bootstrap_new_tickers(_service(store), ["TSLA"])
    assert done == []
    assert "TSLA" in caplog.text and "stored no summary" in caplog.text


def test_a_run_that_stores_a_row_is_counted():
    store = _Store()
    with patch.object(scheduler_workers, "run_team_for_ticker", lambda svc, team, msg, **k: store.upsert_summary("TSLA")):
        assert scheduler_workers.bootstrap_new_tickers(_service(store), ["TSLA"]) == ["TSLA"]


def test_the_writer_warns_when_the_answer_has_no_json_block(caplog):
    with caplog.at_level(logging.WARNING):
        assert write_ticker_summaries("plain prose, no block", ticker_summary_store=_Store(), source_run_id="r1") == []
    assert "no parseable" in caplog.text and "r1" in caplog.text
