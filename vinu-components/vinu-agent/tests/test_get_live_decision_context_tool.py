import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from vinu_agent.tools.get_live_decision_context_tool import GetLiveDecisionContextTool


def _tool(services_config: dict | None = None, config=None) -> GetLiveDecisionContextTool:
    tool = GetLiveDecisionContextTool()
    tool._services_config = services_config or {}
    tool._config = config
    return tool


def _resp(json_body):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = json_body
    resp.raise_for_status = MagicMock()
    return resp


class TestGetLiveDecisionContextTool:
    def test_requires_ticker_and_strategy_id(self) -> None:
        tool = _tool()
        result = json.loads(tool.execute())
        assert result["status"] == "error"

    def test_composes_all_four_sources_into_one_response(self) -> None:
        tool = _tool()

        def _get(url, **kwargs):
            if "/live/decision-context/" in url:
                return _resp({
                    "status": "ok", "stage": "ready_to_execute", "trigger_id": "trig_abc",
                    "live_snapshot": {"adx_14": 17.8, "rsi_14": 55.0},
                })
            if "/live/decisions/" in url:
                return _resp({
                    "status": "ok", "count": 1,
                    "decisions": [{"decision": "SKIP", "reasoning": "evidence was thin last time", "trigger_id": "trig_prior"}],
                })
            if "/strategy/strategies/" in url:
                return _resp({
                    "name": "sma_cross",
                    "must_conditions": [{"source": "live_indicators", "key": "sma_5_gt_sma_50", "operator": "eq", "value": True}],
                    "confirmation_conditions": [],
                    "precondition": {"description": "market quiet before cross", "defined": True, "tested": False},
                })
            if "/research/unconfirmed-moves" in url:
                return _resp({"status": "ok", "events": [], "count": 0})
            if "/reflection/beliefs/notable" in url:
                return _resp({"beliefs": [], "count": 0})
            raise AssertionError(f"unexpected URL: {url}")

        with patch("httpx.get", side_effect=_get), \
              patch(
                  "vinu_agent.tools.get_live_decision_context_tool.GetSignalEvidenceTool.execute",
                  return_value=json.dumps({"status": "ok", "symbol": "AAPL", "count": 3, "outcomes_recorded": 2, "triggers": [
                      {"must_condition": ["live_indicators.sma_5_gt_sma_50_eq_True"], "outcome_recorded_at": "t"},
                      {"must_condition": ["live_indicators.sma_5_gt_sma_50_eq_True"], "outcome_recorded_at": "t"},
                      {"must_condition": ["live_indicators.sma_5_gt_sma_50_eq_True"], "outcome_recorded_at": None},
                  ]}),
              ):
            result = json.loads(tool.execute(ticker="aapl", strategy_id="sma_cross"))

        assert result["status"] == "ok"
        assert result["ticker"] == "AAPL"
        assert result["stage"] == "ready_to_execute"
        assert result["trigger_id"] == "trig_abc"
        assert result["live_snapshot"]["adx_14"] == 17.8
        assert result["precondition"]["defined"] is True
        assert result["precondition"]["tested"] is False
        assert result["signal_evidence_summary"]["count"] == 3
        assert result["past_live_decisions"][0]["decision"] == "SKIP"
        assert result["past_live_decisions"][0]["reasoning"] == "evidence was thin last time"
        assert result["unconfirmed_moves"] == []
        assert result["reflection_notes"] == []

    def test_never_computes_a_win_rate_or_confidence_score(self) -> None:
        """Same honesty rule get_signal_evidence/get_move_evidence already
        commit to -- Phase 3/Layer 4's bucket table doesn't exist yet
        (07-bucket-table-deferred.md)."""
        tool = _tool()
        with patch("httpx.get", return_value=_resp({})), \
             patch(
                 "vinu_agent.tools.get_live_decision_context_tool.GetSignalEvidenceTool.execute",
                 return_value=json.dumps({"status": "ok", "symbol": "AAPL", "count": 0, "outcomes_recorded": 0, "triggers": []}),
             ):
            result = json.loads(tool.execute(ticker="AAPL", strategy_id="sma_cross"))
        dumped = json.dumps(result).lower()
        assert "win_rate" not in dumped
        assert "confidence_score" not in dumped

    def test_a_failed_fetch_degrades_to_empty_not_a_crash(self) -> None:
        tool = _tool()
        with patch("httpx.get", side_effect=ConnectionError("down")), \
             patch(
                 "vinu_agent.tools.get_live_decision_context_tool.GetSignalEvidenceTool.execute",
                 return_value=json.dumps({"status": "ok", "symbol": "AAPL", "count": 0, "outcomes_recorded": 0, "triggers": []}),
             ):
            result = json.loads(tool.execute(ticker="AAPL", strategy_id="sma_cross"))
        assert result["status"] == "ok"
        assert result["stage"] is None
        assert result["live_snapshot"] == {}


class TestMaturityStatusFollowUp:
    """high-expectations follow-up, point #3: live_decision_agent's real
    context source consults the system maturity tier, opt-in via
    AgentConfig.live_decision_maturity_scaling_enabled."""

    def _base_get(self, url, **kwargs):
        if "/live/decision-context/" in url:
            return _resp({"status": "ok", "stage": "ready_to_execute", "trigger_id": "trig_abc", "live_snapshot": {}})
        if "/live/decisions/" in url:
            return _resp({"status": "ok", "count": 0, "decisions": []})
        if "/strategy/strategies/" in url:
            return _resp({"name": "sma_cross", "must_conditions": [], "confirmation_conditions": [], "precondition": {}})
        if "/research/maturity/status" in url:
            return _resp({"tier": "early_live", "n_real_trades": 8, "n_paper_trading_days": 40,
                           "directional_accuracy": 0.55, "regime_coverage": ["trend"]})
        if "/research/unconfirmed-moves" in url:
            return _resp({"status": "ok", "events": [], "count": 0})
        if "/reflection/beliefs/notable" in url:
            return _resp({"beliefs": [], "count": 0})
        raise AssertionError(f"unexpected URL: {url}")

    def test_disabled_by_default_never_calls_the_research_api(self) -> None:
        tool = _tool()  # config=None -> knob off

        def _get(url, **kwargs):
            if "/research/maturity/status" in url:
                raise AssertionError("should not fetch maturity status when disabled")
            return self._base_get(url, **kwargs)

        with patch("httpx.get", side_effect=_get), \
             patch(
                 "vinu_agent.tools.get_live_decision_context_tool.GetSignalEvidenceTool.execute",
                 return_value=json.dumps({"status": "ok", "symbol": "AAPL", "count": 0, "outcomes_recorded": 0, "triggers": []}),
             ):
            result = json.loads(tool.execute(ticker="AAPL", strategy_id="sma_cross"))
        assert result["maturity_status"] == {}

    def test_enabled_includes_the_real_tier_and_evidence(self, tmp_path) -> None:
        cfg = SimpleNamespace(live_decision_maturity_scaling_enabled=True)
        tool = _tool(config=cfg)
        mock_store = MagicMock()

        with patch("httpx.get", side_effect=self._base_get), \
             patch(
                 "vinu_agent.tools.get_live_decision_context_tool.GetSignalEvidenceTool.execute",
                 return_value=json.dumps({"status": "ok", "symbol": "AAPL", "count": 0, "outcomes_recorded": 0, "triggers": []}),
             ), \
             patch(
                 "vinu_agent.tools.get_live_decision_context_tool._get_maturity_consultation_store",
                 return_value=mock_store,
             ):
            result = json.loads(tool.execute(ticker="AAPL", strategy_id="sma_cross"))

        assert result["maturity_status"]["tier"] == "early_live"
        assert result["maturity_status"]["n_real_trades"] == 8
        assert mock_store.record.called
        kwargs = mock_store.record.call_args.kwargs
        assert kwargs["consumer"] == "live_decision"
        assert kwargs["tier"] == "early_live"
        assert kwargs["action_taken"] == "context_included"
        assert kwargs["scope_key"] == "AAPL:sma_cross"

    def test_enabled_but_research_api_unreachable_fails_open_to_empty(self) -> None:
        cfg = SimpleNamespace(live_decision_maturity_scaling_enabled=True)
        tool = _tool(config=cfg)
        mock_store = MagicMock()

        def _get(url, **kwargs):
            if "/research/maturity/status" in url:
                raise ConnectionError("down")
            return self._base_get(url, **kwargs)

        with patch("httpx.get", side_effect=_get), \
             patch(
                 "vinu_agent.tools.get_live_decision_context_tool.GetSignalEvidenceTool.execute",
                 return_value=json.dumps({"status": "ok", "symbol": "AAPL", "count": 0, "outcomes_recorded": 0, "triggers": []}),
             ), \
             patch(
                 "vinu_agent.tools.get_live_decision_context_tool._get_maturity_consultation_store",
                 return_value=mock_store,
             ):
            result = json.loads(tool.execute(ticker="AAPL", strategy_id="sma_cross"))

        assert result["maturity_status"] == {}
        kwargs = mock_store.record.call_args.kwargs
        assert kwargs["action_taken"] == "no_change_status_unavailable"
        assert kwargs["tier"] == "unknown"


class TestUnconfirmedMovesFollowUp:
    """A2 fix: live_decision context carries Track 2's unconfirmed moves
    (real moves no must-condition watched for) -- fails open to []."""

    def _base_get(self, url, **kwargs):
        if "/live/decision-context/" in url:
            return _resp({"status": "ok", "stage": "ready_to_execute", "trigger_id": "trig_abc", "live_snapshot": {}})
        if "/live/decisions/" in url:
            return _resp({"status": "ok", "count": 0, "decisions": []})
        if "/strategy/strategies/" in url:
            return _resp({"name": "sma_cross", "must_conditions": [], "confirmation_conditions": [], "precondition": {}})
        if "/research/unconfirmed-moves" in url:
            return _resp({"status": "ok", "count": 1, "events": [
                {"symbol": "AAPL", "direction": "up", "price_move": 0.03,
                 "confirmed_by_track1": False},
            ]})
        if "/reflection/beliefs/notable" in url:
            return _resp({"beliefs": [], "count": 0})
        raise AssertionError(f"unexpected URL: {url}")

    def test_unconfirmed_moves_included_when_api_returns_events(self) -> None:
        tool = _tool()
        with patch("httpx.get", side_effect=self._base_get), \
              patch(
                  "vinu_agent.tools.get_live_decision_context_tool.GetSignalEvidenceTool.execute",
                  return_value=json.dumps({"status": "ok", "symbol": "AAPL", "count": 0, "outcomes_recorded": 0, "triggers": []}),
              ):
            result = json.loads(tool.execute(ticker="AAPL", strategy_id="sma_cross"))
        assert result["status"] == "ok"
        assert len(result["unconfirmed_moves"]) == 1
        assert result["unconfirmed_moves"][0]["confirmed_by_track1"] is False

    def test_unconfirmed_fetch_failure_degrades_to_empty_list(self) -> None:
        tool = _tool()

        def _get(url, **kwargs):
            if "/research/unconfirmed-moves" in url:
                raise ConnectionError("down")
            return self._base_get(url, **kwargs)

        with patch("httpx.get", side_effect=_get), \
              patch(
                  "vinu_agent.tools.get_live_decision_context_tool.GetSignalEvidenceTool.execute",
                  return_value=json.dumps({"status": "ok", "symbol": "AAPL", "count": 0, "outcomes_recorded": 0, "triggers": []}),
              ):
            result = json.loads(tool.execute(ticker="AAPL", strategy_id="sma_cross"))
        assert result["status"] == "ok"
        assert result["unconfirmed_moves"] == []


class TestReflectionNotesFollowUp:
    """A6 fix: live-decision context carries currently notable reflection
    beliefs as advisory notes -- fails open to []."""

    def _base_get(self, url, **kwargs):
        if "/live/decision-context/" in url:
            return _resp({"status": "ok", "stage": "ready_to_execute", "trigger_id": "trig_abc", "live_snapshot": {}})
        if "/live/decisions/" in url:
            return _resp({"status": "ok", "count": 0, "decisions": []})
        if "/strategy/strategies/" in url:
            return _resp({"name": "sma_cross", "must_conditions": [], "confirmation_conditions": [], "precondition": {}})
        if "/research/unconfirmed-moves" in url:
            return _resp({"status": "ok", "events": [], "count": 0})
        if "/reflection/beliefs/notable" in url:
            return _resp({"beliefs": [
                {"analyst_name": "regime_drift", "cluster": "Regime",
                 "scope_type": "system", "scope_key": "market", "severity": "notable"},
            ], "count": 1})
        raise AssertionError(f"unexpected URL: {url}")

    def test_notable_beliefs_included_as_advisory_notes(self) -> None:
        tool = _tool()
        with patch("httpx.get", side_effect=self._base_get), \
              patch(
                  "vinu_agent.tools.get_live_decision_context_tool.GetSignalEvidenceTool.execute",
                  return_value=json.dumps({"status": "ok", "symbol": "AAPL", "count": 0, "outcomes_recorded": 0, "triggers": []}),
              ):
            result = json.loads(tool.execute(ticker="AAPL", strategy_id="sma_cross"))
        assert result["status"] == "ok"
        assert len(result["reflection_notes"]) == 1
        assert result["reflection_notes"][0]["analyst_name"] == "regime_drift"

    def test_beliefs_fetch_failure_degrades_to_empty_list(self) -> None:
        tool = _tool()

        def _get(url, **kwargs):
            if "/reflection/beliefs/notable" in url:
                raise ConnectionError("down")
            return self._base_get(url, **kwargs)

        with patch("httpx.get", side_effect=_get), \
              patch(
                  "vinu_agent.tools.get_live_decision_context_tool.GetSignalEvidenceTool.execute",
                  return_value=json.dumps({"status": "ok", "symbol": "AAPL", "count": 0, "outcomes_recorded": 0, "triggers": []}),
              ):
            result = json.loads(tool.execute(ticker="AAPL", strategy_id="sma_cross"))
        assert result["status"] == "ok"
        assert result["reflection_notes"] == []


class TestUncertaintyInContext:
    """v2 B2: the tool attaches one read-only uncertainty assessment; it never changes the other fields."""

    def _run(self, context_body, evidence):
        tool = _tool()

        def _get(url, **kwargs):
            if "/live/decision-context/" in url:
                return _resp(context_body)
            if "/strategy/strategies/" in url:
                return _resp({"name": "s", "precondition": {"description": "x", "defined": True, "tested": True}})
            return _resp({})

        with patch("httpx.get", side_effect=_get), \
             patch("vinu_agent.tools.get_live_decision_context_tool.GetSignalEvidenceTool.execute", return_value=json.dumps(evidence)):
            return json.loads(tool.execute(ticker="AAPL", strategy_id="s"))

    def test_high_novelty_and_thin_evidence_are_reported_high(self) -> None:
        out = self._run({"stage": "ready_to_execute", "live_snapshot": {"a": 1}, "novelty": {"status": "ok", "novelty_high": True}},
                        {"status": "ok", "count": 0, "outcomes_recorded": 0, "triggers": []})
        assert out["uncertainty"]["level"] == "high" and "novelty_high" in out["uncertainty"]["reasons"]
        assert out["live_snapshot"] == {"a": 1}

    def test_missing_snapshot_and_unavailable_evidence_are_named(self) -> None:
        out = self._run({}, {"status": "error"})
        assert {"live_snapshot", "signal_evidence"} <= set(out["uncertainty"]["missing_inputs"])


class TestEvidenceFilteredToTheStrategysOwnCondition:
    """features-logic-checking D4: rows recorded for other conditions on the same ticker must not count."""

    OWN = [{"source": "live_indicators", "key": "adx_14", "operator": "gt", "value": 20}]
    OWN_NAME = "live_indicators.adx_14_gt_20"

    def _summary(self):
        return {"status": "ok", "symbol": "AAPL", "count": 4, "outcomes_recorded": 3, "triggers": [
            {"must_condition": [self.OWN_NAME], "outcome_recorded_at": "t"},
            {"must_condition": [self.OWN_NAME], "outcome_recorded_at": None},
            {"must_condition": "sma5_cross_sma50", "outcome_recorded_at": "t"},     # the angle backfill, another condition
            {"must_condition": ["sma5_cross_sma50"], "outcome_recorded_at": "t"},
        ]}

    def test_only_rows_with_the_strategys_own_name_are_kept_and_recounted(self):
        from vinu_agent.tools.get_live_decision_context_tool import _filter_to_strategy_conditions
        out = _filter_to_strategy_conditions(self._summary(), self.OWN)
        assert out["count"] == 2 and out["outcomes_recorded"] == 1
        assert out["all_conditions_count"] == 4 and out["filtered_to_strategy"] is True
        assert out["strategy_conditions"] == [self.OWN_NAME]

    def test_a_strategy_with_no_evidence_of_its_own_now_shows_zero_outcomes(self):
        from vinu_agent.tools.get_live_decision_context_tool import _filter_to_strategy_conditions
        other = [{"source": "live_indicators", "key": "rsi_14", "operator": "lt", "value": 30}]
        out = _filter_to_strategy_conditions(self._summary(), other)
        assert out["count"] == 0 and out["outcomes_recorded"] == 0

    def test_without_a_known_condition_list_nothing_is_filtered_and_it_says_so(self):
        from vinu_agent.tools.get_live_decision_context_tool import _filter_to_strategy_conditions
        for unknown in (None, [], "x"):
            out = _filter_to_strategy_conditions(self._summary(), unknown)
            assert out["count"] == 4 and out["filtered_to_strategy"] is False

    def test_an_error_summary_passes_through_untouched(self):
        from vinu_agent.tools.get_live_decision_context_tool import _filter_to_strategy_conditions
        s = {"status": "error", "error": "x"}
        assert _filter_to_strategy_conditions(s, self.OWN) == s

    def test_the_name_rule_is_the_one_the_live_poller_records_under(self):
        from vinu_infra.condition_names import condition_name
        assert condition_name(self.OWN[0]) == self.OWN_NAME
