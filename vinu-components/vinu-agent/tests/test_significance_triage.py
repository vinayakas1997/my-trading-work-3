"""Tests for Significance Triage -- Phase 7 (New-talk-agents/new-thinking/
new-restructure/phases/phase-7-significance-triage/). See
agent/significance_triage.py.
"""

from __future__ import annotations

import asyncio
import re
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vinu_agent.agent.significance_triage import (
    ChannelTarget,
    REJECTED_PATTERN_MIN_COUNT,
    REJECTED_PATTERN_WINDOW_HOURS,
    SignificanceFlagStore,
    deliver_flag,
    detect_large_funding_pattern,
    detect_repeated_rejection_pattern,
    detect_thesis_contradiction_pattern,
    format_flag_message,
    record_human_override,
)
from vinu_agent.storage.ticker_ledger import TickerLedgerStore

_HEX12 = re.compile(r"^[0-9a-f]{12}$")


@pytest.fixture
def flag_store():
    path = Path(tempfile.mktemp(suffix=".db"))
    store = SignificanceFlagStore(path)
    yield store
    store.close()
    try:
        path.unlink(missing_ok=True)
    except PermissionError:
        pass


@pytest.fixture
def ticker_ledger_store():
    path = Path(tempfile.mktemp(suffix=".db"))
    store = TickerLedgerStore(path)
    yield store
    store.close()
    try:
        path.unlink(missing_ok=True)
    except PermissionError:
        pass


class TestSignificanceFlagStore:
    def test_create_flag_gets_standard_id_format(self, flag_store) -> None:
        flag = flag_store.create_flag("AAPL", "repeated_rejection", "3 rejections in 24h")
        assert _HEX12.match(flag.flag_id)
        assert flag.resolved is False

    def test_get_flag_roundtrips(self, flag_store) -> None:
        created = flag_store.create_flag("AAPL", "repeated_rejection", "detail")
        fetched = flag_store.get_flag(created.flag_id)
        assert fetched.ticker == "AAPL"
        assert fetched.reason == "repeated_rejection"

    def test_unknown_flag_id_returns_none(self, flag_store) -> None:
        assert flag_store.get_flag("nonexistent") is None

    def test_mark_responded_resolves_the_flag(self, flag_store) -> None:
        flag = flag_store.create_flag("AAPL", "repeated_rejection", "detail")
        updated = flag_store.mark_responded(flag.flag_id, "acknowledged, tightening limits")
        assert updated.resolved is True
        assert updated.response_text == "acknowledged, tightening limits"
        assert updated.responded_at != ""

    def test_unanswered_flag_does_not_error_or_retry(self, flag_store) -> None:
        """No response, ever -- must not raise or enter any error state."""
        flag = flag_store.create_flag("AAPL", "repeated_rejection", "detail")
        fetched = flag_store.get_flag(flag.flag_id)
        assert fetched.resolved is False
        assert fetched.responded_at == ""

    def test_response_rate_tracks_from_day_one(self, flag_store) -> None:
        f1 = flag_store.create_flag("AAPL", "r", "d")
        flag_store.create_flag("MSFT", "r", "d")
        flag_store.mark_responded(f1.flag_id, "ok")

        stats = flag_store.response_rate()
        assert stats["total"] == 2
        assert stats["responded"] == 1
        assert stats["rate"] == pytest.approx(0.5)

    def test_response_rate_with_no_flags_is_none_not_a_crash(self, flag_store) -> None:
        stats = flag_store.response_rate()
        assert stats["total"] == 0
        assert stats["rate"] is None


class TestDetectRepeatedRejectionPattern:
    def test_routine_decision_not_flagged(self, ticker_ledger_store) -> None:
        ticker_ledger_store.add_event(
            ticker="AAPL", stage="risk_gatekeeper", event_type="REJECTED", text="r1",
        )
        result = detect_repeated_rejection_pattern("AAPL", ticker_ledger_store)
        assert result is None  # only 1, below the default min_count of 3

    def test_repeated_rejection_pattern_flagged(self, ticker_ledger_store) -> None:
        for i in range(3):
            ticker_ledger_store.add_event(
                ticker="AAPL", stage="risk_gatekeeper", event_type="REJECTED", text=f"r{i}",
            )
        result = detect_repeated_rejection_pattern("AAPL", ticker_ledger_store)
        assert result is not None
        assert result["ticker"] == "AAPL"
        assert result["count"] == 3
        assert result["window_hours"] == REJECTED_PATTERN_WINDOW_HOURS

    def test_pattern_detection_reads_ticker_ledger_directly(self, ticker_ledger_store) -> None:
        """Events written through any path (no Significance-Triage-owned
        counter update involved) are still correctly detected -- proves
        detection queries the Ledger itself."""
        for i in range(REJECTED_PATTERN_MIN_COUNT):
            ticker_ledger_store.add_event(
                ticker="AAPL", stage="risk_gatekeeper", event_type="REJECTED",
                text=f"rejection {i}", ref_id=f"art_{i}", source="watchlist",
            )
        result = detect_repeated_rejection_pattern("AAPL", ticker_ledger_store)
        assert result is not None
        assert result["count"] == REJECTED_PATTERN_MIN_COUNT

    def test_other_tickers_do_not_bleed_into_the_count(self, ticker_ledger_store) -> None:
        for i in range(3):
            ticker_ledger_store.add_event(
                ticker="MSFT", stage="risk_gatekeeper", event_type="REJECTED", text=f"r{i}",
            )
        result = detect_repeated_rejection_pattern("AAPL", ticker_ledger_store)
        assert result is None

    def test_other_event_types_do_not_count_toward_the_pattern(self, ticker_ledger_store) -> None:
        for i in range(3):
            ticker_ledger_store.add_event(ticker="AAPL", stage="risk_gatekeeper", event_type="PEND", text=f"p{i}")
        result = detect_repeated_rejection_pattern("AAPL", ticker_ledger_store)
        assert result is None


class TestDetectLargeFundingPattern:
    def test_below_threshold_not_flagged(self, ticker_ledger_store) -> None:
        ticker_ledger_store.add_event(
            ticker="AAPL", stage="capital_allocator", event_type="funded",
            text="capital_allocator funded and activated, amount=1000.0",
        )
        result = detect_large_funding_pattern("AAPL", ticker_ledger_store, threshold=50000.0)
        assert result is None

    def test_at_or_above_threshold_flagged(self, ticker_ledger_store) -> None:
        ticker_ledger_store.add_event(
            ticker="AAPL", stage="capital_allocator", event_type="funded",
            text="capital_allocator funded and activated, amount=75000.0",
        )
        result = detect_large_funding_pattern("AAPL", ticker_ledger_store, threshold=50000.0)
        assert result is not None
        assert result["ticker"] == "AAPL"
        assert result["amount"] == 75000.0
        assert result["threshold"] == 50000.0

    def test_exactly_at_threshold_flagged(self, ticker_ledger_store) -> None:
        ticker_ledger_store.add_event(
            ticker="AAPL", stage="capital_allocator", event_type="funded",
            text="capital_allocator funded and activated, amount=50000.0",
        )
        result = detect_large_funding_pattern("AAPL", ticker_ledger_store, threshold=50000.0)
        assert result is not None

    def test_pendblock_events_not_counted_as_funded(self, ticker_ledger_store) -> None:
        ticker_ledger_store.add_event(
            ticker="AAPL", stage="capital_allocator", event_type="PENDBLOCK",
            text="funding decided (amount=99999.0) but Kill Switch engaged for scope='AAPL'",
        )
        result = detect_large_funding_pattern("AAPL", ticker_ledger_store, threshold=50000.0)
        assert result is None

    def test_other_tickers_do_not_bleed_in(self, ticker_ledger_store) -> None:
        ticker_ledger_store.add_event(
            ticker="MSFT", stage="capital_allocator", event_type="funded",
            text="capital_allocator funded and activated, amount=99999.0",
        )
        result = detect_large_funding_pattern("AAPL", ticker_ledger_store, threshold=50000.0)
        assert result is None

    def test_unparseable_amount_skipped_not_raised(self, ticker_ledger_store) -> None:
        ticker_ledger_store.add_event(
            ticker="AAPL", stage="capital_allocator", event_type="funded",
            text="capital_allocator funded and activated, amount=oops",
        )
        result = detect_large_funding_pattern("AAPL", ticker_ledger_store, threshold=50000.0)
        assert result is None


class TestDetectThesisContradictionPattern:
    def test_no_contradiction_not_flagged(self, ticker_ledger_store) -> None:
        result = detect_thesis_contradiction_pattern("AAPL", ticker_ledger_store)
        assert result is None

    def test_single_contradiction_flagged_by_default(self, ticker_ledger_store) -> None:
        """min_count defaults to 1 -- no repeated-pattern threshold is
        invented for this detector, unlike repeated_rejection's 3."""
        ticker_ledger_store.add_event(
            ticker="AAPL", stage="debrief", event_type="thesis_contradicted",
            text="Position closed. Entry ~$10.00, exit ~$8.00 -> realized P&L $-200.00.",
            ref_id="hyp_1",
        )
        result = detect_thesis_contradiction_pattern("AAPL", ticker_ledger_store)
        assert result is not None
        assert result["ticker"] == "AAPL"
        assert result["count"] == 1

    def test_other_tickers_do_not_bleed_in(self, ticker_ledger_store) -> None:
        ticker_ledger_store.add_event(
            ticker="MSFT", stage="debrief", event_type="thesis_contradicted", text="x",
        )
        result = detect_thesis_contradiction_pattern("AAPL", ticker_ledger_store)
        assert result is None

    def test_supporting_close_events_do_not_count(self, ticker_ledger_store) -> None:
        """Only event_type="thesis_contradicted" counts -- a supporting
        close never writes this event at all (see debrief.py)."""
        ticker_ledger_store.add_event(
            ticker="AAPL", stage="risk_gatekeeper", event_type="REJECTED", text="unrelated",
        )
        result = detect_thesis_contradiction_pattern("AAPL", ticker_ledger_store)
        assert result is None


class TestFlagNeverBlocksTheUnderlyingAction:
    def test_detection_and_flagging_never_touch_the_strategy_store(
        self, ticker_ledger_store, flag_store,
    ) -> None:
        """Structural proof, not just a claim: detect_repeated_rejection_
        pattern and SignificanceFlagStore.create_flag take no
        SqliteStrategyStore argument at all -- there is no code path here
        that could roll back or gate a real funding/rejection decision.
        The action a flag describes has already happened and is already
        reflected in storage by the time detection even runs (real
        REJECTED events only exist in TickerLedger once
        risk_gatekeeper_hook.py already wrote them, after the verdict was
        already final)."""
        for i in range(3):
            ticker_ledger_store.add_event(
                ticker="AAPL", stage="risk_gatekeeper", event_type="REJECTED", text=f"r{i}",
            )

        pattern = detect_repeated_rejection_pattern("AAPL", ticker_ledger_store)
        assert pattern is not None
        flag = flag_store.create_flag("AAPL", "repeated_rejection", f"{pattern['count']} rejections")

        # The flag now exists, entirely independent of and downstream from
        # the real REJECTED events -- nothing above could have reversed them.
        assert flag_store.get_flag(flag.flag_id) is not None
        assert ticker_ledger_store.count_events("AAPL", event_type="REJECTED") == 3


class TestFlagMessageAndDelivery:
    def test_format_flag_message_includes_flag_id_and_detail(self, flag_store) -> None:
        flag = flag_store.create_flag("AAPL", "repeated_rejection", "3 rejections in 24h -- max_position_pct")
        text = format_flag_message(flag)
        assert flag.flag_id in text
        assert "AAPL" in text
        assert "3 rejections in 24h" in text

    def test_flag_delivered_via_existing_channel_wiring(self, flag_store) -> None:
        flag = flag_store.create_flag("AAPL", "repeated_rejection", "detail")
        mock_channel = MagicMock()
        mock_channel.send_message = MagicMock(return_value=asyncio.sleep(0))

        asyncio.run(deliver_flag(flag, [ChannelTarget(mock_channel, "chat-1")]))

        mock_channel.send_message.assert_called_once()
        args = mock_channel.send_message.call_args
        assert args[0][0] == "chat-1"
        assert flag.flag_id in args[0][1]

    def test_multi_channel_delivery_shares_one_flag_id(self, flag_store) -> None:
        flag = flag_store.create_flag("AAPL", "repeated_rejection", "detail")
        discord_channel = MagicMock()
        discord_channel.send_message = MagicMock(return_value=asyncio.sleep(0))
        telegram_channel = MagicMock()
        telegram_channel.send_message = MagicMock(return_value=asyncio.sleep(0))

        targets = [ChannelTarget(discord_channel, "d-chat"), ChannelTarget(telegram_channel, "t-chat")]
        asyncio.run(deliver_flag(flag, targets))

        discord_text = discord_channel.send_message.call_args[0][1]
        telegram_text = telegram_channel.send_message.call_args[0][1]
        assert flag.flag_id in discord_text
        assert flag.flag_id in telegram_text
        # Both messages reference the SAME flag_id -- a human's response via either
        # channel resolves the same underlying flag record, not two independent ones.
        assert flag.flag_id in discord_text and flag.flag_id in telegram_text

    def test_one_channel_failing_does_not_block_the_others(self, flag_store) -> None:
        flag = flag_store.create_flag("AAPL", "repeated_rejection", "detail")
        failing_channel = MagicMock()

        async def _raise(*a, **kw):
            raise ConnectionError("discord down")
        failing_channel.send_message = _raise

        working_channel = MagicMock()
        working_channel.send_message = MagicMock(return_value=asyncio.sleep(0))

        targets = [ChannelTarget(failing_channel, "d-chat"), ChannelTarget(working_channel, "t-chat")]
        asyncio.run(deliver_flag(flag, targets))  # must not raise

        working_channel.send_message.assert_called_once()


def _force_in_process_unavailable():
    return patch(
        "vinu_agent.broker.research_link.get_hypothesis_registry",
        side_effect=RuntimeError("not available"),
    )


class TestRecordHumanOverrideInProcess:
    def test_writes_real_evidence_to_existing_hypothesis(self) -> None:
        from vinu_research.hypothesis_registry import HypothesisRegistry
        from vinu_research.models import Hypothesis

        registry = HypothesisRegistry(path=Path(tempfile.mktemp(suffix=".json")))
        h = Hypothesis.create(title="t", thesis="th")
        registry.create(h)

        with patch("vinu_agent.broker.research_link.get_hypothesis_registry", return_value=registry):
            ok = record_human_override(
                "http://research-api:8087", h.hypothesis_id, "flag_abc123",
                source="human_override", conclusion="contradicts", reasoning="human disagreed",
            )

        assert ok is True
        stored = registry.get(h.hypothesis_id)
        assert stored.evidence[0].source == "human_override"
        assert stored.evidence[0].ref_id == "flag_abc123"
        assert stored.evidence[0].conclusion == "contradicts"

    def test_unknown_hypothesis_falls_back_to_http(self) -> None:
        from vinu_research.hypothesis_registry import HypothesisRegistry

        registry = HypothesisRegistry(path=Path(tempfile.mktemp(suffix=".json")))
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        with patch(
            "vinu_agent.broker.research_link.get_hypothesis_registry", return_value=registry,
        ), patch("httpx.post", return_value=mock_resp) as mock_post:
            ok = record_human_override(
                "http://research-api:8087", "does_not_exist", "flag_abc123",
                source="human_override", conclusion="contradicts", reasoning="x",
            )
        assert ok is True
        mock_post.assert_called_once()


class TestRecordHumanOverrideHttpFallback:
    def test_writes_override_with_correct_tag_and_ref_id(self) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        with _force_in_process_unavailable(), patch("httpx.post", return_value=mock_resp) as mock_post:
            ok = record_human_override(
                "http://research-api:8087", "hyp_1", "flag_abc123",
                source="human_override", conclusion="contradicts", reasoning="human disagreed",
            )
        assert ok is True
        _, kwargs = mock_post.call_args
        payload = kwargs["json"]
        assert payload["source"] == "human_override"
        assert payload["ref_id"] == "flag_abc123"
        assert payload["conclusion"] == "contradicts"

    def test_override_write_requires_source_tag(self) -> None:
        with pytest.raises(TypeError):
            record_human_override(  # type: ignore[call-arg]
                "http://research-api:8087", "hyp_1", "flag_abc123",
                conclusion="contradicts", reasoning="human disagreed",
            )

    def test_wrong_source_value_raises(self) -> None:
        with pytest.raises(ValueError):
            record_human_override(
                "http://research-api:8087", "hyp_1", "flag_abc123",
                source="human", conclusion="contradicts", reasoning="x",
            )

    def test_http_failure_returns_false_not_raise(self) -> None:
        with _force_in_process_unavailable(), patch("httpx.post", side_effect=ConnectionError("down")):
            ok = record_human_override(
                "http://research-api:8087", "hyp_1", "flag_abc123",
                source="human_override", conclusion="contradicts", reasoning="x",
            )
        assert ok is False


class TestMissingChannelFailureMode:
    """Task 03 acceptance (step 5): missing/invalid notification credentials
    must produce a clear log, not a silent drop of the detection and not a
    worker crash. The no-channel-configured branch of _run_detector_for_ticker
    is exactly that path."""

    def test_flag_created_and_logged_warning_when_no_channel_configured(
        self, ticker_ledger_store, flag_store, caplog
    ) -> None:
        from vinu_agent.agent.scheduler_workers import _run_detector_for_ticker

        ticker_ledger_store.add_event(
            "AAPL", "risk_gatekeeper", "REJECTED", "max_position_pct",
        )
        ticker_ledger_store.add_event(
            "AAPL", "risk_gatekeeper", "REJECTED", "max_position_pct",
        )
        ticker_ledger_store.add_event(
            "AAPL", "risk_gatekeeper", "REJECTED", "max_position_pct",
        )

        with caplog.at_level("WARNING"):
            flag = asyncio.run(_run_detector_for_ticker(
                "AAPL", "repeated_risk_gatekeeper_rejection",
                lambda hit: f"{hit['count']} REJECTED verdicts",
                lambda t: detect_repeated_rejection_pattern(t, ticker_ledger_store),
                flag_store=flag_store, targets=[],
            ))

        # Detection and flagging still happen with no channel configured...
        assert flag is not None
        assert flag_store.get_flag(flag.flag_id) is not None
        # ...and the missing delivery target is loud, never silent.
        assert any("no channel is configured to deliver it" in rec.message for rec in caplog.records)
