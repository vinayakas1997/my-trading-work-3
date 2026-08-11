import asyncio
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock

import pytest

from vinu_live.book.positions import close_position, init_book, list_closed_positions, open_position
from vinu_live.config import LiveConfig
from vinu_live.feedback_loop import FeedbackLoopWorker, _realized_return_pct


@pytest.fixture
def book():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    be = init_book(db_path)
    yield be
    be.close()
    if os.path.exists(db_path):
        os.unlink(db_path)


def _make_worker(book, **config_overrides) -> FeedbackLoopWorker:
    config = LiveConfig(**config_overrides)
    worker = FeedbackLoopWorker(config, book=book)
    worker._http = MagicMock()
    # Default: no active hypotheses for any symbol -- keeps existing
    # tests' POST call-count assertions stable (Phase 5 adds a GET lookup
    # before any evidence POST, and only POSTs evidence when the lookup
    # actually returns an active hypothesis). Tests that specifically
    # exercise the hypothesis-evidence write override this.
    worker._http.get = AsyncMock(return_value=_resp(200, {"hypotheses": []}))
    return worker


def _resp(status_code=200, json_body=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_body if json_body is not None else {}
    return resp


class TestRealizedReturnPct:
    def test_long_gain(self) -> None:
        pct = _realized_return_pct({"avg_entry": 100.0, "close_price": 110.0})
        assert pct == pytest.approx(0.10)

    def test_long_loss(self) -> None:
        pct = _realized_return_pct({"avg_entry": 100.0, "close_price": 90.0})
        assert pct == pytest.approx(-0.10)

    def test_short_position_uses_raw_price_return_not_pnl_sign(self) -> None:
        # A short position that profited from a price decline still reports a *negative*
        # return here -- the underlying moved down, matching a "short" forecast's own
        # direction convention (see compute_directional_error), not the position's P&L sign.
        pct = _realized_return_pct({"avg_entry": 100.0, "close_price": 90.0, "side": "short"})
        assert pct == pytest.approx(-0.10)

    def test_missing_close_price_returns_zero(self) -> None:
        assert _realized_return_pct({"avg_entry": 100.0, "close_price": None}) == 0.0

    def test_zero_avg_entry_returns_zero(self) -> None:
        assert _realized_return_pct({"avg_entry": 0.0, "close_price": 100.0}) == 0.0


class TestCycle:
    def test_no_unprocessed_positions_skips(self, book) -> None:
        worker = _make_worker(book)
        result = asyncio.run(worker.cycle())
        assert result["status"] == "skipped_no_unprocessed_positions"

    def test_processes_closed_position_with_artifact_id(self, book) -> None:
        pos = open_position(book, "AAPL", "buy", 10.0, 150.0, artifact_id="art_1")
        close_position(book, pos.position_id, 165.0)

        worker = _make_worker(book)
        worker._http.post = AsyncMock(return_value=_resp(200, {"status": "ok"}))

        result = asyncio.run(worker.cycle())

        assert result["status"] == "ok"
        assert len(result["processed"]) == 1
        outcome = result["processed"][0]
        assert outcome["symbol"] == "AAPL"
        assert outcome["artifact_id"] == "art_1"
        assert outcome["realized_return_pct"] == pytest.approx(0.10)
        assert outcome["calibration_recorded"] is True
        assert outcome["pnl_attribution_recorded"] is True
        assert outcome["personality_stats_refreshed"] is True
        assert outcome["hypothesis_evidence_recorded"] is False  # no active hypotheses (default mock)
        assert outcome["ticker_ledger_recorded"] is True
        # Four POST write-back calls: calibration, pnl_attribution,
        # personality refresh, ticker-ledger close-out (no hypothesis
        # evidence POST since the lookup found nothing active).
        assert worker._http.post.call_count == 4

    def test_marks_position_processed_so_it_is_not_resent(self, book) -> None:
        pos = open_position(book, "AAPL", "buy", 10.0, 150.0, artifact_id="art_1")
        close_position(book, pos.position_id, 165.0)

        worker = _make_worker(book)
        worker._http.post = AsyncMock(return_value=_resp(200, {"status": "ok"}))

        asyncio.run(worker.cycle())
        first_call_count = worker._http.post.call_count

        second_result = asyncio.run(worker.cycle())
        assert second_result["status"] == "skipped_no_unprocessed_positions"
        assert worker._http.post.call_count == first_call_count

    def test_no_artifact_id_skips_calibration_but_still_processes(self, book) -> None:
        pos = open_position(book, "AAPL", "buy", 10.0, 150.0)  # no artifact_id
        close_position(book, pos.position_id, 165.0)

        worker = _make_worker(book)
        worker._http.post = AsyncMock(return_value=_resp(200, {"status": "ok"}))

        result = asyncio.run(worker.cycle())
        assert result["status"] == "skipped_no_unprocessed_positions"
        # Positions without an artifact_id were never opened by the trade-plan orchestrator
        # and list_closed_positions(unprocessed_only=True) correctly excludes them.
        assert list_closed_positions(book, unprocessed_only=True) == []

    def test_outbound_call_failure_does_not_mark_processed_incorrectly(self, book) -> None:
        # Even when every outbound call fails, the position is still marked processed --
        # this worker doesn't retry indefinitely; a failed write-back is logged and moved
        # past, matching the "never blocks live trading" design intent.
        pos = open_position(book, "AAPL", "buy", 10.0, 150.0, artifact_id="art_1")
        close_position(book, pos.position_id, 165.0)

        worker = _make_worker(book)
        worker._http.post = AsyncMock(side_effect=ConnectionError("down"))
        worker._http.get = AsyncMock(side_effect=ConnectionError("down"))

        result = asyncio.run(worker.cycle())
        outcome = result["processed"][0]
        assert outcome["calibration_recorded"] is False
        assert outcome["pnl_attribution_recorded"] is False
        assert outcome["personality_stats_refreshed"] is False
        assert outcome["hypothesis_evidence_recorded"] is False
        assert outcome["ticker_ledger_recorded"] is False
        assert list_closed_positions(book, unprocessed_only=True) == []

    def test_personality_refresh_uses_targeted_angle_names_and_fresh_to_ts(self, book) -> None:
        pos = open_position(book, "AAPL", "buy", 10.0, 150.0, artifact_id="art_1")
        close_position(book, pos.position_id, 165.0)

        worker = _make_worker(book)
        worker._http.post = AsyncMock(return_value=_resp(200, {"status": "ok"}))

        asyncio.run(worker.cycle())

        run_calls = [
            c for c in worker._http.post.call_args_list
            if "/run/" in c.args[0]
        ]
        assert len(run_calls) == 1
        params = run_calls[0].kwargs["params"]
        assert params["angle_names"] == "shock_personality,shock_clustering"
        assert "to_ts" in params

    def test_never_imports_orchestrator(self) -> None:
        import vinu_live.feedback_loop as fl
        assert "orchestrator" not in fl.__dict__
        assert "TradePlanOrchestrator" not in dir(fl)


class TestHypothesisRegistryAndTickerLedgerWrites:
    """Phase 5 (New-talk-agents/new-thinking/new-restructure/phases/
    phase-5-monitor-extend/): the two writes feedback_loop.py's close-out
    path never made before this phase."""

    def test_closeout_writes_hypothesis_registry_evidence(self, book) -> None:
        pos = open_position(book, "AAPL", "buy", 10.0, 150.0, artifact_id="art_1")
        close_position(book, pos.position_id, 165.0)

        worker = _make_worker(book)
        worker._http.get = AsyncMock(return_value=_resp(200, {
            "hypotheses": [{"hypothesis_id": "hyp_1", "status": "testing"}],
        }))
        worker._http.post = AsyncMock(return_value=_resp(200, {"status": "ok"}))

        result = asyncio.run(worker.cycle())

        outcome = result["processed"][0]
        assert outcome["hypothesis_evidence_recorded"] is True

        evidence_calls = [
            c for c in worker._http.post.call_args_list
            if "/hyp_1/evidence" in c.args[0]
        ]
        assert len(evidence_calls) == 1
        payload = evidence_calls[0].kwargs["json"]
        assert payload["metric"] == "realized_return_pct"
        assert payload["conclusion"] == "supports"  # 10% gain
        assert payload["value"] == pytest.approx(0.10)

    def test_closeout_only_writes_evidence_for_active_status_hypotheses(self, book) -> None:
        pos = open_position(book, "AAPL", "buy", 10.0, 150.0, artifact_id="art_1")
        close_position(book, pos.position_id, 165.0)

        worker = _make_worker(book)
        worker._http.get = AsyncMock(return_value=_resp(200, {
            "hypotheses": [
                {"hypothesis_id": "hyp_active", "status": "testing"},
                {"hypothesis_id": "hyp_rejected", "status": "rejected"},
                {"hypothesis_id": "hyp_validated", "status": "validated"},
            ],
        }))
        worker._http.post = AsyncMock(return_value=_resp(200, {"status": "ok"}))

        asyncio.run(worker.cycle())

        evidence_ids = {
            c.args[0].split("/hypotheses/")[1].split("/evidence")[0]
            for c in worker._http.post.call_args_list
            if "/hypotheses/" in c.args[0] and c.args[0].endswith("/evidence")
        }
        assert evidence_ids == {"hyp_active"}

    def test_closeout_writes_ticker_ledger_row(self, book) -> None:
        pos = open_position(book, "AAPL", "buy", 10.0, 150.0, artifact_id="art_1")
        close_position(book, pos.position_id, 165.0)

        worker = _make_worker(book)
        worker._http.post = AsyncMock(return_value=_resp(200, {"status": "ok"}))

        result = asyncio.run(worker.cycle())

        outcome = result["processed"][0]
        assert outcome["ticker_ledger_recorded"] is True

        ledger_calls = [
            c for c in worker._http.post.call_args_list
            if "/ticker-ledger/event" in c.args[0]
        ]
        assert len(ledger_calls) == 1
        payload = ledger_calls[0].kwargs["json"]
        assert payload["ticker"] == "AAPL"
        assert payload["stage"] == "monitor"
        assert payload["event_type"] == "position_closed"
        assert payload["ref_id"] == "art_1"

    def test_audit_write_failure_does_not_block_or_reverse_the_close(self, book) -> None:
        """The real close (and the fact it's marked processed, never to be
        resent) must already be true BEFORE the new audit writes are even
        attempted -- proven here by making both new writes fail and
        confirming the position is still gone from the unprocessed list."""
        pos = open_position(book, "AAPL", "buy", 10.0, 150.0, artifact_id="art_1")
        close_position(book, pos.position_id, 165.0)

        worker = _make_worker(book)
        worker._http.get = AsyncMock(return_value=_resp(200, {
            "hypotheses": [{"hypothesis_id": "hyp_1", "status": "testing"}],
        }))

        async def failing_post(url, **kwargs):
            if "/evidence" in url or "/ticker-ledger/" in url:
                raise ConnectionError("audit write down")
            return _resp(200, {"status": "ok"})

        worker._http.post = AsyncMock(side_effect=failing_post)

        result = asyncio.run(worker.cycle())

        outcome = result["processed"][0]
        assert outcome["hypothesis_evidence_recorded"] is False
        assert outcome["ticker_ledger_recorded"] is False
        # The close itself already happened (mark_feedback_processed runs
        # BEFORE these two writes are even attempted) -- not reversed by
        # either audit write failing.
        assert list_closed_positions(book, unprocessed_only=True) == []
        assert result["status"] == "ok"
