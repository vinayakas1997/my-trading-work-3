from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from vinu_live.trade_plan.rebalance_intake import RebalanceRequestQueue


@pytest.fixture
def db_path() -> Path:
    path = Path(tempfile.mktemp(suffix=".db"))
    yield path
    path.unlink(missing_ok=True)


@pytest.fixture
def queue(db_path: Path) -> RebalanceRequestQueue:
    q = RebalanceRequestQueue(str(db_path))
    yield q
    q.close()


class TestRebalanceRequestQueue:
    def test_submit_then_pending_for(self, queue: RebalanceRequestQueue) -> None:
        queue.submit("aapl", "free capital for Y")
        request = queue.pending_for("AAPL")
        assert request is not None
        assert request.symbol == "AAPL"
        assert request.reason == "free capital for Y"

    def test_no_request_returns_none(self, queue: RebalanceRequestQueue) -> None:
        assert queue.pending_for("AAPL") is None

    def test_newer_request_replaces_older_for_same_symbol(self, queue: RebalanceRequestQueue) -> None:
        queue.submit("AAPL", "first reason")
        queue.submit("AAPL", "second reason")
        request = queue.pending_for("AAPL")
        assert request.reason == "second reason"

    def test_consume_removes_the_pending_request(self, queue: RebalanceRequestQueue) -> None:
        queue.submit("AAPL", "reason")
        queue.consume("AAPL")
        assert queue.pending_for("AAPL") is None

    def test_consume_unknown_symbol_does_not_raise(self, queue: RebalanceRequestQueue) -> None:
        queue.consume("MSFT")  # no-op, must not raise

    def test_symbols_are_independent(self, queue: RebalanceRequestQueue) -> None:
        queue.submit("AAPL", "reason a")
        queue.consume("MSFT")
        assert queue.pending_for("AAPL") is not None


class TestRebalanceRequestHistory:
    """Analysis U (25-A-Y-details/03-execution-money-flow.md) needs a
    historical log of past critical=True requests -- consume() deleting
    the working-queue row can't answer that alone."""

    def test_consume_archives_the_request_into_history(self, queue: RebalanceRequestQueue) -> None:
        queue.submit("AAPL", "free capital", critical=True)
        queue.consume("AAPL")
        history = queue.history_for("AAPL")
        assert len(history) == 1
        assert history[0].symbol == "AAPL"
        assert history[0].reason == "free capital"
        assert history[0].critical is True

    def test_consuming_unknown_symbol_writes_no_history(self, queue: RebalanceRequestQueue) -> None:
        queue.consume("MSFT")
        assert queue.history_for("MSFT") == []

    def test_history_survives_after_the_pending_row_is_gone(self, queue: RebalanceRequestQueue) -> None:
        queue.submit("AAPL", "reason", critical=False)
        queue.consume("AAPL")
        assert queue.pending_for("AAPL") is None
        assert len(queue.history_for("AAPL")) == 1

    def test_repeated_submit_consume_cycles_accumulate_history(self, queue: RebalanceRequestQueue) -> None:
        queue.submit("AAPL", "first", critical=True)
        queue.consume("AAPL")
        queue.submit("AAPL", "second", critical=False)
        queue.consume("AAPL")
        history = queue.history_for("AAPL")
        assert len(history) == 2
        assert {h.reason for h in history} == {"first", "second"}

    def test_all_history_spans_every_symbol(self, queue: RebalanceRequestQueue) -> None:
        queue.submit("AAPL", "a", critical=True)
        queue.consume("AAPL")
        queue.submit("MSFT", "b", critical=False)
        queue.consume("MSFT")
        symbols = {h.symbol for h in queue.all_history()}
        assert symbols == {"AAPL", "MSFT"}

    def test_history_visible_across_instances(self, db_path: Path) -> None:
        writer = RebalanceRequestQueue(str(db_path))
        writer.submit("AAPL", "reason", critical=True)
        writer.consume("AAPL")
        writer.close()

        reader = RebalanceRequestQueue(str(db_path))
        history = reader.history_for("AAPL")
        reader.close()

        assert len(history) == 1
        assert history[0].critical is True


class TestRebalanceRequestQueuePersistsAcrossInstances:
    """The actual bug being closed: server/app.py's HTTP route and the
    trade-plan-worker's own cron loop each construct their own
    TradePlanOrchestrator (and therefore their own RebalanceRequestQueue
    Python object) -- a request must still be visible to a SECOND queue
    instance pointed at the same on-disk path, not just to the instance
    that wrote it."""

    def test_a_request_submitted_by_one_instance_is_visible_to_another(self, db_path: Path) -> None:
        writer = RebalanceRequestQueue(str(db_path))
        writer.submit("AAPL", "unwind to fund a better candidate")
        writer.close()

        reader = RebalanceRequestQueue(str(db_path))
        request = reader.pending_for("AAPL")
        reader.close()

        assert request is not None
        assert request.reason == "unwind to fund a better candidate"

    def test_consume_by_one_instance_is_visible_to_another(self, db_path: Path) -> None:
        writer = RebalanceRequestQueue(str(db_path))
        writer.submit("AAPL", "reason")
        writer.close()

        consumer = RebalanceRequestQueue(str(db_path))
        consumer.consume("AAPL")
        consumer.close()

        reader = RebalanceRequestQueue(str(db_path))
        request = reader.pending_for("AAPL")
        reader.close()

        assert request is None
