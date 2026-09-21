"""Tests for the scheduler-triggered real team invocation -- Phase 9
scheduler-wiring (New-talk-agents/new-thinking/new-restructure/phases/
phase-9-scheduler-wiring/). See agent/scheduler_workers.py.
"""

from __future__ import annotations

import asyncio
import json
import tempfile
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vinu_agent.agent.planner_triage_hook import PlannerTriageResult
from vinu_agent.agent.scheduler_workers import (
    TRIAGE_FRESHNESS_FRESH,
    TRIAGE_FRESHNESS_STALE,
    TRIAGE_FRESHNESS_UNKNOWN,
    _map_parallel,
    bootstrap_new_tickers,
    build_channel_targets,
    discover_new_tickers,
    hypothesis_reader_for,
    make_planner_on_yes,
    make_summary_agent_fn,
    run_llm_failure_check,
    run_significance_cycle,
    run_team_for_ticker,
)
from vinu_agent.agent.significance_triage import (
    LLM_FAILURE_SENTINEL_TICKER,
    REJECTED_PATTERN_MIN_COUNT,
    SignificanceFlagStore,
)
from vinu_agent.config import AgentConfig
from vinu_agent.storage.ticker_ledger import TickerLedgerStore
from vinu_infra.telemetry import LLMCallRecord, TelemetryStore


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

    def test_parallel_bootstrap_overlaps_ticker_team_runs(self) -> None:
        # Real int on config.summary_parallelism engages the pool (MagicMock
        # default coerces to serial, which is what the other tests assert).
        service = _fake_service()
        service.config.summary_parallelism = 3
        service.ticker_summary_store = _fake_summary_store([])
        gate = threading.Barrier(3, timeout=5)

        def _run(svc, team, task, *, session_id):
            # Only completes if all three run concurrently -- a serial loop
            # would hang and trip the barrier timeout.
            gate.wait()
            return {"status": "completed", "content": "ok"}

        with patch("vinu_agent.agent.scheduler_workers.run_team_for_ticker", side_effect=_run):
            bootstrapped = bootstrap_new_tickers(service, ["AAPL", "MSFT", "NVDA"])

        assert bootstrapped == ["AAPL", "MSFT", "NVDA"]


class TestMapParallel:
    def test_input_order_preserved_even_when_completion_is_not(self) -> None:
        import time as _time

        def slow_first(x):
            if x == 0:
                _time.sleep(0.05)
            return x

        assert _map_parallel(slow_first, [0, 1, 2], max_workers=3) == [0, 1, 2]

    def test_single_item_or_worker_count_one_is_serial(self) -> None:
        calls: list[int] = []

        def fn(x):
            calls.append(x)
            return x * 2

        assert _map_parallel(fn, [5], max_workers=8) == [10]
        assert _map_parallel(fn, [1, 2], max_workers=1) == [2, 4]
        assert calls == [5, 1, 2]

    def test_non_numeric_worker_count_falls_back_to_serial(self) -> None:
        assert _map_parallel(lambda x: x, [1, 2], max_workers=MagicMock()) == [1, 2]


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
        # out of the LLM's prose. Trust overlay keys always present (here
        # all unrated: no calibration store in test env).
        assert meta == {"angles_with_data": 5, "angle_count": 28,
                        "low_trust_angles": [], "rated_angles": 0,
                        "unrated_angles": 0, "angle_digest": {},
                        "cluster_digest": {}, "cross_cluster": {},
                        "cluster_anomalies": {}}
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
        assert meta == {"angles_with_data": 0, "angle_count": 28,
                        "low_trust_angles": [], "rated_angles": 0, "unrated_angles": 0,
                        "angle_digest": {}, "cluster_digest": {}, "cross_cluster": {},
                        "cluster_anomalies": {}}

    def test_angle_digest_is_built_from_every_angle_with_data(self) -> None:
        """Regression for the '2 of 28 angles' gate-conflict: angles_data
        was fetched here all along, but only its two counts ever escaped
        this function -- see high-expectations gate-conflict audit."""
        service = _fake_service()
        angles_json = json.dumps({
            "ticker": "AAPL", "angle_count": 2, "angles_with_data": 2,
            "angles": {
                "trend_lifecycle": {"row_count": 1, "data": [{"stage": "mature"}]},
                "regime_analysis": {"row_count": 1, "data": [{"regime": "bull"}]},
            },
        })

        with patch("vinu_agent.tools.angles_tool.GetAllAnglesTool.execute", return_value=angles_json), \
             patch("vinu_agent.agent.scheduler_workers.run_team_for_ticker",
                   return_value={"status": "completed", "content": "ok"}):
            fn = make_summary_agent_fn(service)
            _, meta = fn("AAPL")

        assert meta["angle_digest"] == {
            "trend_lifecycle": {"stage": "mature"},
            "regime_analysis": {"regime": "bull"},
        }

    def test_dedupe_cache_hit_carries_stored_angle_digest_forward(self) -> None:
        service = _fake_service()
        from datetime import datetime, timezone

        existing = MagicMock()
        existing.updated_at = datetime.now(timezone.utc).isoformat()
        existing.summary = "cached summary"
        existing.angles_with_data = 2
        existing.angle_count = 2
        existing.angle_digest = {"trend_lifecycle": {"stage": "mature"}}
        service.ticker_summary_store.get_summary.return_value = existing

        with patch("vinu_agent.agent.scheduler_workers.run_team_for_ticker") as mock_run:
            fn = make_summary_agent_fn(service)
            summary_text, meta = fn("AAPL")

        assert summary_text == "cached summary"
        assert meta["angle_digest"] == {"trend_lifecycle": {"stage": "mature"}}
        mock_run.assert_not_called()

    def test_dedupe_cache_hit_carries_stored_cluster_digest_forward(self) -> None:
        service = _fake_service()
        from datetime import datetime, timezone

        existing = MagicMock()
        existing.updated_at = datetime.now(timezone.utc).isoformat()
        existing.summary = "cached summary"
        existing.angles_with_data = 2
        existing.angle_count = 2
        existing.angle_digest = {}
        existing.cluster_digest = {"B": "cached cluster read"}
        existing.cross_cluster = {"redundant_clusters": ["G"]}
        service.ticker_summary_store.get_summary.return_value = existing

        with patch("vinu_agent.agent.scheduler_workers.run_team_for_ticker") as mock_run:
            fn = make_summary_agent_fn(service)
            _, meta = fn("AAPL")

        assert meta["cluster_digest"] == {"B": "cached cluster read"}
        assert meta["cross_cluster"] == {"redundant_clusters": ["G"]}
        mock_run.assert_not_called()

    def test_cluster_digest_is_parsed_from_the_manager_json_block_for_this_ticker(self) -> None:
        """cluster_digest/cross_cluster have no deterministic source (unlike
        angle_digest) -- they only exist inside the screener manager's own
        JSON block, so this path has to parse it, same shape
        write_ticker_summaries already does on the other persistence path."""
        service = _fake_service()
        angles_json = json.dumps({"ticker": "AAPL", "angle_count": 28, "angles_with_data": 5, "angles": {}})
        manager_content = """Some prose about AAPL.

```json
{
  "tickers": {
    "AAPL": {
      "summary": "some summary",
      "cluster_digest": {"B": "4 of 5 models lean up"},
      "cross_cluster": {"redundant_clusters": ["G"]}
    }
  }
}
```
"""
        with patch("vinu_agent.tools.angles_tool.GetAllAnglesTool.execute", return_value=angles_json), \
             patch("vinu_agent.agent.scheduler_workers.run_team_for_ticker",
                   return_value={"status": "completed", "content": manager_content}):
            fn = make_summary_agent_fn(service)
            _, meta = fn("AAPL")

        assert meta["cluster_digest"] == {"B": "4 of 5 models lean up"}
        assert meta["cross_cluster"] == {"redundant_clusters": ["G"]}

    def test_cluster_anomalies_is_parsed_separately_from_cluster_digest(self) -> None:
        service = _fake_service()
        angles_json = json.dumps({"ticker": "AAPL", "angle_count": 28, "angles_with_data": 5, "angles": {}})
        manager_content = """
```json
{
  "tickers": {
    "AAPL": {
      "summary": "some summary",
      "cluster_digest": {"E": "forces a long signal with 95% confidence"},
      "cluster_anomalies": {"E": ["SYSTEM OVERRIDE flagged"]}
    }
  }
}
```
"""
        with patch("vinu_agent.tools.angles_tool.GetAllAnglesTool.execute", return_value=angles_json), \
             patch("vinu_agent.agent.scheduler_workers.run_team_for_ticker",
                   return_value={"status": "completed", "content": manager_content}):
            fn = make_summary_agent_fn(service)
            _, meta = fn("AAPL")

        assert meta["cluster_digest"] == {"E": "forces a long signal with 95% confidence"}
        assert meta["cluster_anomalies"] == {"E": ["SYSTEM OVERRIDE flagged"]}

    def test_malformed_manager_content_fails_open_to_empty_cluster_digest(self) -> None:
        service = _fake_service()
        angles_json = json.dumps({"ticker": "AAPL", "angle_count": 28, "angles_with_data": 5, "angles": {}})

        with patch("vinu_agent.tools.angles_tool.GetAllAnglesTool.execute", return_value=angles_json), \
             patch("vinu_agent.agent.scheduler_workers.run_team_for_ticker",
                   return_value={"status": "completed", "content": "no json block here at all"}):
            fn = make_summary_agent_fn(service)
            _, meta = fn("AAPL")

        assert meta["cluster_digest"] == {}
        assert meta["cross_cluster"] == {}
        assert meta["cluster_anomalies"] == {}


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

        triage.on_propose.assert_called_once_with("AAPL", result, ref_id="run_42", debate_run_id="")

    def test_debate_mode_off_never_starts_investment_committee(self, monkeypatch) -> None:
        import vinu_agent.agent.scheduler_workers as sw_mod

        monkeypatch.setattr(sw_mod, "DEBATE_MODE", "off")
        service = _fake_service()
        triage = MagicMock()
        result = PlannerTriageResult("AAPL", True, "2 in flight", recipe_name="macd_cross")
        triage.check.return_value = result

        with patch("vinu_agent.agent.scheduler_workers.run_team_for_ticker",
                   return_value={"run_id": "run_42"}):
            on_yes = make_planner_on_yes(service, triage)
            on_yes("AAPL", MagicMock())

        service.swarm_runtime.create_run.assert_not_called()
        triage.on_propose.assert_called_once_with("AAPL", result, ref_id="run_42", debate_run_id="")

    def test_debate_mode_full_starts_investment_committee_and_links_run_id(self, monkeypatch) -> None:
        import vinu_agent.agent.scheduler_workers as sw_mod

        monkeypatch.setattr(sw_mod, "DEBATE_MODE", "full")
        service = _fake_service()
        service.swarm_runtime.create_run.return_value = MagicMock(run_id="debate_99")
        triage = MagicMock()
        result = PlannerTriageResult("AAPL", True, "2 in flight", recipe_name="macd_cross")
        triage.check.return_value = result

        with patch("vinu_agent.agent.scheduler_workers.run_team_for_ticker",
                   return_value={"run_id": "run_42"}):
            on_yes = make_planner_on_yes(service, triage)
            on_yes("AAPL", MagicMock())

        service.swarm_runtime.create_run.assert_called_once_with(
            "investment_committee", {"symbol": "AAPL"},
        )
        service.swarm_runtime.start_run.assert_called_once_with("debate_99")

    def test_debate_mode_full_failure_does_not_block_research_handoff(self, monkeypatch) -> None:
        import vinu_agent.agent.scheduler_workers as sw_mod

        monkeypatch.setattr(sw_mod, "DEBATE_MODE", "full")
        service = _fake_service()
        service.swarm_runtime.create_run.side_effect = RuntimeError("preset not found")
        triage = MagicMock()
        result = PlannerTriageResult("AAPL", True, "2 in flight", recipe_name="macd_cross")
        triage.check.return_value = result

        with patch("vinu_agent.agent.scheduler_workers.run_team_for_ticker",
                   return_value={"run_id": "run_42"}):
            on_yes = make_planner_on_yes(service, triage)
            on_yes("AAPL", MagicMock())  # must not raise

        triage.on_propose.assert_called_once_with(
            "AAPL", result, ref_id="run_42", debate_run_id="",
        )


class TestStrategyEnhancerContext:
    """missing-pieces-of-system/startegy-enhancer/01-plan.md section 5 --
    the freed-K-cap-slot candidate gets real sibling/failure context."""

    def test_env_unset_ships_inert(self, monkeypatch) -> None:
        monkeypatch.delenv("VINU_STRATEGY_EVAL_DATA_ROOT", raising=False)
        service = _fake_service()
        triage = MagicMock()
        result = PlannerTriageResult("AAPL", True, "reason", recipe_name="macd_cross")
        triage.check.return_value = result

        with patch("vinu_agent.agent.scheduler_workers.run_team_for_ticker",
                   return_value={"run_id": "run_42"}) as mock_run:
            on_yes = make_planner_on_yes(service, triage)
            on_yes("AAPL", MagicMock())

        task_text = mock_run.call_args[0][2]
        assert "in flight for this ticker" not in task_text
        assert "Most recent rejected candidate" not in task_text

    def test_in_flight_siblings_and_recent_rejection_added_to_task(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("VINU_STRATEGY_EVAL_DATA_ROOT", str(tmp_path))
        from vinu_infra.strategy_evaluation import StrategyEvaluationStore

        store = StrategyEvaluationStore(tmp_path / "strategy_evaluation.db")
        store.write_step_result(
            artifact_id="sibling-1", ticker="AAPL", step_name="risk_critic",
            step_order=1, verdict="PASS",
        )
        store.write_step_result(
            artifact_id="rejected-1", ticker="AAPL", step_name="promotion_bar",
            step_order=2, verdict="FAIL", reasoning="deflated_sharpe 0.1 below threshold 0.3",
        )

        service = _fake_service()
        triage = MagicMock()
        result = PlannerTriageResult("AAPL", True, "reason", recipe_name="macd_cross")
        triage.check.return_value = result

        with patch("vinu_agent.agent.scheduler_workers.run_team_for_ticker",
                   return_value={"run_id": "run_42"}) as mock_run:
            on_yes = make_planner_on_yes(service, triage)
            on_yes("AAPL", MagicMock())

        task_text = mock_run.call_args[0][2]
        assert "sibling-1" in task_text
        assert "in flight for this ticker" in task_text
        assert "promotion_bar" in task_text
        assert "deflated_sharpe 0.1 below threshold 0.3" in task_text

    def test_no_ticker_history_adds_nothing(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("VINU_STRATEGY_EVAL_DATA_ROOT", str(tmp_path))
        from vinu_infra.strategy_evaluation import StrategyEvaluationStore

        StrategyEvaluationStore(tmp_path / "strategy_evaluation.db")  # creates the schema, no rows

        service = _fake_service()
        triage = MagicMock()
        result = PlannerTriageResult("AAPL", True, "reason", recipe_name="macd_cross")
        triage.check.return_value = result

        with patch("vinu_agent.agent.scheduler_workers.run_team_for_ticker",
                   return_value={"run_id": "run_42"}) as mock_run:
            on_yes = make_planner_on_yes(service, triage)
            on_yes("AAPL", MagicMock())

        task_text = mock_run.call_args[0][2]
        assert "in flight for this ticker" not in task_text
        assert "Most recent rejected candidate" not in task_text

class TestPlannerTriageFreshnessLogging:
    """Analysis R (25-A-Y-details/05-governance-freshness.md): logs, at
    each real Planner triage event, whether the run it acted on was
    already stale/errored -- checked live, since `ticker_summaries` is
    deliberately never versioned and can't answer this after the fact."""

    def test_no_reader_means_no_freshness_logging(self) -> None:
        service = _fake_service()
        triage = MagicMock()
        triage.check.return_value = PlannerTriageResult("AAPL", False, "at K-cap")

        on_yes = make_planner_on_yes(service, triage)  # run_log_reader defaults to None
        on_yes("AAPL", MagicMock(run_id_seen="run_1"))

        freshness_calls = [
            c for c in service.ticker_ledger.add_event.call_args_list
            if c.kwargs.get("event_type") in {
                TRIAGE_FRESHNESS_FRESH, TRIAGE_FRESHNESS_STALE, TRIAGE_FRESHNESS_UNKNOWN,
            }
        ]
        assert freshness_calls == []

    def test_logs_fresh_when_run_ids_match(self) -> None:
        service = _fake_service()
        triage = MagicMock()
        triage.check.return_value = PlannerTriageResult("AAPL", False, "at K-cap")
        reader = MagicMock()
        reader.latest_run_id.return_value = "run_5"

        on_yes = make_planner_on_yes(service, triage, run_log_reader=reader)
        on_yes("AAPL", MagicMock(run_id_seen="run_5"))

        call = service.ticker_ledger.add_event.call_args_list[0]
        assert call.kwargs["event_type"] == TRIAGE_FRESHNESS_FRESH
        assert "fresh" in call.kwargs["text"]
        assert "STALE" not in call.kwargs["text"]

    def test_logs_stale_when_latest_run_differs(self) -> None:
        service = _fake_service()
        triage = MagicMock()
        triage.check.return_value = PlannerTriageResult("AAPL", False, "at K-cap")
        reader = MagicMock()
        reader.latest_run_id.return_value = "run_9"

        on_yes = make_planner_on_yes(service, triage, run_log_reader=reader)
        on_yes("AAPL", MagicMock(run_id_seen="run_5"))

        call = service.ticker_ledger.add_event.call_args_list[0]
        assert call.kwargs["event_type"] == TRIAGE_FRESHNESS_STALE
        assert "STALE" in call.kwargs["text"]
        assert "run_5" in call.kwargs["text"]
        assert "run_9" in call.kwargs["text"]

    def test_reader_exception_logs_unknown_and_does_not_raise(self) -> None:
        service = _fake_service()
        triage = MagicMock()
        triage.check.return_value = PlannerTriageResult("AAPL", False, "at K-cap")
        reader = MagicMock()
        reader.latest_run_id.side_effect = RuntimeError("vinu-initial-analysis down")

        on_yes = make_planner_on_yes(service, triage, run_log_reader=reader)
        on_yes("AAPL", MagicMock(run_id_seen="run_5"))  # must not raise

        call = service.ticker_ledger.add_event.call_args_list[0]
        assert call.kwargs["event_type"] == TRIAGE_FRESHNESS_UNKNOWN
        assert "failed" in call.kwargs["text"]

    def test_freshness_logged_even_when_triage_declines_to_propose(self) -> None:
        """The freshness question is about the triage EVENT (did Planner
        look at this ticker at all), not about whether it proposed
        something -- must fire even on a "no" from PlannerTriage."""
        service = _fake_service()
        triage = MagicMock()
        triage.check.return_value = PlannerTriageResult("AAPL", False, "at K-cap")
        reader = MagicMock()
        reader.latest_run_id.return_value = "run_5"

        on_yes = make_planner_on_yes(service, triage, run_log_reader=reader)
        on_yes("AAPL", MagicMock(run_id_seen="run_5"))

        assert service.ticker_ledger.add_event.call_count == 1

    def test_ledger_write_failure_does_not_block_the_real_triage(self) -> None:
        service = _fake_service()
        service.ticker_ledger.add_event.side_effect = RuntimeError("db locked")
        triage = MagicMock()
        result = PlannerTriageResult("AAPL", True, "2 in flight", recipe_name="macd_cross")
        triage.check.return_value = result
        reader = MagicMock()
        reader.latest_run_id.return_value = "run_5"

        with patch("vinu_agent.agent.scheduler_workers.run_team_for_ticker",
                   return_value={"run_id": "run_42"}) as mock_run:
            on_yes = make_planner_on_yes(service, triage, run_log_reader=reader)
            on_yes("AAPL", MagicMock(run_id_seen="run_5"))  # must not raise

        mock_run.assert_called_once()


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


@pytest.fixture
def telemetry_store():
    path = Path(tempfile.mktemp(suffix=".db"))
    store = TelemetryStore(path)
    yield store
    store.close()
    try:
        path.unlink(missing_ok=True)
    except PermissionError:
        pass


def _record_llm_call(store: TelemetryStore, *, success: bool) -> None:
    store.record_llm_call(LLMCallRecord(
        service="test", model="test-model", base_url="http://fake/v1",
        prompt_tokens=1, completion_tokens=1, total_tokens=2,
        token_count_source="provider", retry_count=0, latency_sec=0.1,
        success=success, outcome="completed" if success else "all_endpoints_failed",
    ))


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


class TestRunLlmFailureCheck:
    """Service-wide counterpart of TestRunSignificanceCycle -- see
    missing-pieces-of-system/llm-configuration-settings-system/."""

    def test_no_failures_raises_no_flag(self, telemetry_store, flag_store) -> None:
        for _ in range(10):
            _record_llm_call(telemetry_store, success=True)
        flag = asyncio.run(run_llm_failure_check(telemetry_store, flag_store, []))
        assert flag is None

    def test_failure_pattern_raises_and_delivers_a_flag(self, telemetry_store, flag_store) -> None:
        from vinu_agent.agent.significance_triage import ChannelTarget

        for _ in range(5):
            _record_llm_call(telemetry_store, success=False)
        channel = _FakeChannel()
        targets = [ChannelTarget(channel, "chat1")]

        flag = asyncio.run(run_llm_failure_check(telemetry_store, flag_store, targets))

        assert flag is not None
        assert flag.ticker == LLM_FAILURE_SENTINEL_TICKER
        assert flag.reason == "llm_failure_rate"
        assert len(channel.sent) == 1
        assert flag_store.get_flag(flag.flag_id) is not None

    def test_flag_still_recorded_with_no_targets_configured(self, telemetry_store, flag_store) -> None:
        for _ in range(5):
            _record_llm_call(telemetry_store, success=False)
        flag = asyncio.run(run_llm_failure_check(telemetry_store, flag_store, []))
        assert flag is not None
        assert flag_store.get_flag(flag.flag_id) is not None

    def test_detection_failure_does_not_raise(self, flag_store) -> None:
        class RaisingTelemetry:
            def recent_llm_calls(self, limit=100, service=None):
                raise RuntimeError("db down")

        flag = asyncio.run(run_llm_failure_check(RaisingTelemetry(), flag_store, []))  # must not raise
        assert flag is None


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
