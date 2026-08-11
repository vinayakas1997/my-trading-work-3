"""Tests for the scheduler-triggered real team invocation -- Phase 9
scheduler-wiring (New-talk-agents/new-thinking/new-restructure/phases/
phase-9-scheduler-wiring/). See agent/scheduler_workers.py.
"""

from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vinu_agent.agent.planner_triage_hook import PlannerTriageResult
from vinu_agent.agent.scheduler_workers import (
    bootstrap_new_tickers,
    build_channel_targets,
    discover_new_tickers,
    hypothesis_reader_for,
    make_planner_on_yes,
    make_summary_agent_fn,
    run_significance_cycle,
    run_team_for_ticker,
)
from vinu_agent.agent.significance_triage import REJECTED_PATTERN_MIN_COUNT, SignificanceFlagStore
from vinu_agent.config import AgentConfig
from vinu_agent.storage.ticker_ledger import TickerLedgerStore


def _fake_service() -> MagicMock:
    service = MagicMock()
    service.config.services = {"vinu_initial_analysis": "http://x"}
    service.config.teams_dir = "/teams"
    return service


class TestRunTeamForTicker:
    def test_constructs_team_manager_for_the_right_team_and_runs_task(self) -> None:
        service = _fake_service()
        with patch("vinu_agent.tools.build_registry", return_value=MagicMock()) as mock_build, \
             patch("vinu_agent.agent.scheduler_workers.TeamManager") as MockManager:
            MockManager.return_value.run.return_value = {"status": "completed", "content": "ok"}

            result = run_team_for_ticker(service, "research", "do the thing", session_id="sess-1")

            assert result == {"status": "completed", "content": "ok"}
            mock_build.assert_called_once()
            team_dir_arg = MockManager.call_args[0][0]
            assert str(team_dir_arg).replace("\\", "/").endswith("teams/research")
            MockManager.return_value.run.assert_called_once_with("do the thing")


def _fake_summary_store(existing_tickers: list[str]) -> MagicMock:
    store = MagicMock()
    store.list_summaries.return_value = [MagicMock(ticker=t) for t in existing_tickers]
    return store


class TestDiscoverNewTickers:
    def test_seed_tickers_not_in_store_are_new(self) -> None:
        store = _fake_summary_store(["AAPL"])
        new = discover_new_tickers(["AAPL", "MSFT"], store)
        assert new == ["MSFT"]

    def test_empty_seed_list_returns_nothing(self) -> None:
        store = _fake_summary_store([])
        assert discover_new_tickers([], store) == []

    def test_all_seed_tickers_already_known_returns_nothing(self) -> None:
        store = _fake_summary_store(["AAPL", "MSFT"])
        assert discover_new_tickers(["AAPL", "MSFT"], store) == []

    def test_case_and_whitespace_normalized(self) -> None:
        store = _fake_summary_store(["AAPL"])
        new = discover_new_tickers([" aapl ", " msft"], store)
        assert new == ["MSFT"]

    def test_duplicate_seed_entries_deduplicated(self) -> None:
        store = _fake_summary_store([])
        new = discover_new_tickers(["MSFT", "MSFT", "AAPL"], store)
        assert new == ["MSFT", "AAPL"]

    def test_blank_entries_ignored(self) -> None:
        store = _fake_summary_store([])
        new = discover_new_tickers(["AAPL", "", "  "], store)
        assert new == ["AAPL"]


class TestBootstrapNewTickers:
    def test_runs_screener_once_per_new_ticker(self) -> None:
        service = _fake_service()
        service.ticker_summary_store = _fake_summary_store(["AAPL"])

        with patch(
            "vinu_agent.agent.scheduler_workers.run_team_for_ticker",
            return_value={"status": "completed", "content": "ok"},
        ) as mock_run:
            bootstrapped = bootstrap_new_tickers(service, ["AAPL", "MSFT", "NVDA"])

        assert bootstrapped == ["MSFT", "NVDA"]
        assert mock_run.call_count == 2
        mock_run.assert_any_call(service, "screener", "Ticker: MSFT", session_id="watchlist-bootstrap-MSFT")
        mock_run.assert_any_call(service, "screener", "Ticker: NVDA", session_id="watchlist-bootstrap-NVDA")

    def test_no_new_tickers_makes_no_calls(self) -> None:
        service = _fake_service()
        service.ticker_summary_store = _fake_summary_store(["AAPL"])

        with patch("vinu_agent.agent.scheduler_workers.run_team_for_ticker") as mock_run:
            bootstrapped = bootstrap_new_tickers(service, ["AAPL"])

        assert bootstrapped == []
        mock_run.assert_not_called()

    def test_one_ticker_failing_does_not_stop_the_others(self) -> None:
        service = _fake_service()
        service.ticker_summary_store = _fake_summary_store([])

        def _run(service, team, task, *, session_id):
            if "MSFT" in task:
                raise RuntimeError("screener down")
            return {"status": "completed", "content": "ok"}

        with patch("vinu_agent.agent.scheduler_workers.run_team_for_ticker", side_effect=_run):
            bootstrapped = bootstrap_new_tickers(service, ["MSFT", "AAPL"])

        assert bootstrapped == ["AAPL"]


class TestMakeSummaryAgentFn:
    def test_returns_llm_text_and_deterministic_angle_meta(self) -> None:
        service = _fake_service()
        angles_json = json.dumps({"ticker": "AAPL", "angle_count": 28, "angles_with_data": 5, "angles": {}})

        with patch("vinu_agent.tools.angles_tool.GetAllAnglesTool.execute", return_value=angles_json), \
             patch("vinu_agent.agent.scheduler_workers.run_team_for_ticker",
                   return_value={"status": "completed", "content": "AAPL summary text"}) as mock_run:
            fn = make_summary_agent_fn(service)
            summary_text, meta = fn("AAPL")

        assert summary_text == "AAPL summary text"
        # Deterministic, from the tool's own real counts -- never parsed
        # out of the LLM's prose.
        assert meta == {"angles_with_data": 5, "angle_count": 28}
        mock_run.assert_called_once_with(service, "screener", "Ticker: AAPL", session_id="summary-refresh-AAPL")

    def test_incomplete_run_returns_empty_summary_not_partial_text(self) -> None:
        service = _fake_service()
        angles_json = json.dumps({"angle_count": 28, "angles_with_data": 0})

        with patch("vinu_agent.tools.angles_tool.GetAllAnglesTool.execute", return_value=angles_json), \
             patch("vinu_agent.agent.scheduler_workers.run_team_for_ticker",
                   return_value={"status": "error", "content": "partial garbage"}):
            fn = make_summary_agent_fn(service)
            summary_text, meta = fn("AAPL")

        assert summary_text == ""
        assert meta == {"angles_with_data": 0, "angle_count": 28}


class TestMakePlannerOnYes:
    def test_skips_handoff_when_triage_says_no(self) -> None:
        service = _fake_service()
        triage = MagicMock()
        triage.check.return_value = PlannerTriageResult("AAPL", False, "at K-cap")

        with patch("vinu_agent.agent.scheduler_workers.run_team_for_ticker") as mock_run:
            on_yes = make_planner_on_yes(service, triage)
            on_yes("AAPL", MagicMock())

        mock_run.assert_not_called()
        triage.on_propose.assert_not_called()

    def test_hands_off_to_research_team_and_records_proposal(self) -> None:
        service = _fake_service()
        triage = MagicMock()
        result = PlannerTriageResult(
            "AAPL", True, "2 in flight", recipe_name="macd_cross",
            prior_rejections=["too correlated with existing book"],
        )
        triage.check.return_value = result

        with patch("vinu_agent.agent.scheduler_workers.run_team_for_ticker",
                   return_value={"status": "completed", "content": "ok", "run_id": "run_42"}) as mock_run:
            on_yes = make_planner_on_yes(service, triage)
            on_yes("AAPL", MagicMock())

        assert mock_run.call_count == 1
        call_args = mock_run.call_args
        assert call_args[0][:2] == (service, "research")
        task_text = call_args[0][2]
        assert "AAPL" in task_text
        assert "macd_cross" in task_text
        assert "too correlated with existing book" in task_text

        triage.on_propose.assert_called_once_with("AAPL", result, ref_id="run_42")


class TestBuildChannelTargets:
    def test_no_config_returns_no_targets(self) -> None:
        config = AgentConfig()
        assert build_channel_targets(config) == []

    def test_telegram_only_when_only_telegram_configured(self) -> None:
        config = AgentConfig(telegram_token="tok", telegram_admin_chat_id="chat1")
        targets = build_channel_targets(config)
        assert len(targets) == 1
        assert targets[0].chat_id == "chat1"

    def test_both_configured_returns_both_independently(self) -> None:
        config = AgentConfig(
            telegram_token="tok", telegram_admin_chat_id="chat1",
            discord_token="dtok", discord_admin_channel_id="999",
        )
        targets = build_channel_targets(config)
        assert len(targets) == 2
        assert {t.chat_id for t in targets} == {"chat1", "999"}

    def test_token_without_chat_id_is_not_enough(self) -> None:
        config = AgentConfig(telegram_token="tok", telegram_admin_chat_id="")
        assert build_channel_targets(config) == []


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


class _FakeChannel:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    async def send_message(self, chat_id: str, text: str) -> None:
        self.sent.append((chat_id, text))


_TEST_FUNDING_THRESHOLD = 50000.0


class TestRunSignificanceCycle:
    def test_no_pattern_raises_no_flag(self, ticker_ledger_store, flag_store) -> None:
        flags = asyncio.run(
            run_significance_cycle(
                ["AAPL"], ticker_ledger_store, flag_store, [], funding_threshold=_TEST_FUNDING_THRESHOLD,
            ),
        )
        assert flags == []

    def test_repeated_rejection_raises_and_delivers_a_flag(self, ticker_ledger_store, flag_store) -> None:
        from vinu_agent.agent.significance_triage import ChannelTarget

        for _ in range(REJECTED_PATTERN_MIN_COUNT):
            ticker_ledger_store.add_event("AAPL", "risk_gatekeeper", "REJECTED", "rejected")

        channel = _FakeChannel()
        targets = [ChannelTarget(channel, "chat1")]

        flags = asyncio.run(
            run_significance_cycle(
                ["AAPL"], ticker_ledger_store, flag_store, targets, funding_threshold=_TEST_FUNDING_THRESHOLD,
            ),
        )

        assert len(flags) == 1
        assert flags[0].ticker == "AAPL"
        assert flags[0].reason == "repeated_risk_gatekeeper_rejection"
        assert len(channel.sent) == 1
        assert channel.sent[0][0] == "chat1"

    def test_large_funding_raises_and_delivers_a_flag(self, ticker_ledger_store, flag_store) -> None:
        from vinu_agent.agent.significance_triage import ChannelTarget

        ticker_ledger_store.add_event(
            "AAPL", "capital_allocator", "funded",
            "capital_allocator funded and activated, amount=75000.0",
        )
        channel = _FakeChannel()
        targets = [ChannelTarget(channel, "chat1")]

        flags = asyncio.run(
            run_significance_cycle(
                ["AAPL"], ticker_ledger_store, flag_store, targets, funding_threshold=_TEST_FUNDING_THRESHOLD,
            ),
        )

        assert len(flags) == 1
        assert flags[0].reason == "large_funding_decision"
        assert len(channel.sent) == 1

    def test_thesis_contradiction_raises_and_delivers_a_flag(self, ticker_ledger_store, flag_store) -> None:
        from vinu_agent.agent.significance_triage import ChannelTarget

        ticker_ledger_store.add_event(
            "AAPL", "debrief", "thesis_contradicted", "close contradicted the thesis",
        )
        channel = _FakeChannel()
        targets = [ChannelTarget(channel, "chat1")]

        flags = asyncio.run(
            run_significance_cycle(
                ["AAPL"], ticker_ledger_store, flag_store, targets, funding_threshold=_TEST_FUNDING_THRESHOLD,
            ),
        )

        assert len(flags) == 1
        assert flags[0].reason == "thesis_contradicting_close"

    def test_all_three_patterns_can_fire_for_the_same_ticker_in_one_cycle(
        self, ticker_ledger_store, flag_store,
    ) -> None:
        for _ in range(REJECTED_PATTERN_MIN_COUNT):
            ticker_ledger_store.add_event("AAPL", "risk_gatekeeper", "REJECTED", "rejected")
        ticker_ledger_store.add_event(
            "AAPL", "capital_allocator", "funded",
            "capital_allocator funded and activated, amount=75000.0",
        )
        ticker_ledger_store.add_event(
            "AAPL", "debrief", "thesis_contradicted", "close contradicted the thesis",
        )

        flags = asyncio.run(
            run_significance_cycle(
                ["AAPL"], ticker_ledger_store, flag_store, [], funding_threshold=_TEST_FUNDING_THRESHOLD,
            ),
        )

        assert {f.reason for f in flags} == {
            "repeated_risk_gatekeeper_rejection", "large_funding_decision", "thesis_contradicting_close",
        }

    def test_flag_still_recorded_with_no_targets_configured(self, ticker_ledger_store, flag_store) -> None:
        for _ in range(REJECTED_PATTERN_MIN_COUNT):
            ticker_ledger_store.add_event("AAPL", "risk_gatekeeper", "REJECTED", "rejected")

        flags = asyncio.run(
            run_significance_cycle(
                ["AAPL"], ticker_ledger_store, flag_store, [], funding_threshold=_TEST_FUNDING_THRESHOLD,
            ),
        )

        assert len(flags) == 1
        assert flag_store.get_flag(flags[0].flag_id) is not None

    def test_detection_failure_for_one_ticker_does_not_abort_the_cycle(self, flag_store) -> None:
        class PartlyRaisingLedger:
            """Raises for AAPL, but reports a real hit for MSFT -- proves
            one ticker's detection failure doesn't stop the rest of the
            watchlist's cycle from completing."""

            def count_events(self, ticker, *, stage=None, event_type=None, since=None):
                if ticker == "AAPL":
                    raise RuntimeError("db down")
                if event_type == "REJECTED":
                    return REJECTED_PATTERN_MIN_COUNT
                return 0

            def get_events(self, ticker):
                if ticker == "AAPL":
                    raise RuntimeError("db down")
                return []

        flags = asyncio.run(
            run_significance_cycle(
                ["AAPL", "MSFT"], PartlyRaisingLedger(), flag_store, [], funding_threshold=_TEST_FUNDING_THRESHOLD,
            ),
        )
        assert len(flags) == 1
        assert flags[0].ticker == "MSFT"


class TestHypothesisReaderFor:
    def test_converts_hypothesis_dataclasses_to_dicts(self) -> None:
        fake_hyp = MagicMock()
        fake_hyp.hypothesis_id = "h1"
        fake_hyp.thesis = "AAPL breaks out on volume"
        fake_hyp.status.value = "rejected"
        fake_hyp.invalidation_reason = "correlated with existing position"

        fake_registry = MagicMock()
        fake_registry.query_by_symbol.return_value = [fake_hyp]

        with patch("vinu_agent.broker.research_link.get_hypothesis_registry", return_value=fake_registry):
            reader = hypothesis_reader_for(_fake_service())
            result = reader.query_by_symbol("AAPL")

        assert result == [{
            "hypothesis_id": "h1", "thesis": "AAPL breaks out on volume",
            "status": "rejected", "invalidation_reason": "correlated with existing position",
        }]
