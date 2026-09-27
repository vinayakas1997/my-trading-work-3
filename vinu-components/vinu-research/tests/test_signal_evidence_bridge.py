"""item #1 (system-wide-audit-and-design/02-open-questions-strategy-and-
simulation.md): Track 1's signal_evidence angle records real must-
condition trigger/outcome data, but nothing fed it back into
HypothesisRegistry -- these tests exercise the real bridge, through both
real stores (SQLite + JSON), not mocks."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from vinu_research.hypothesis_registry import HypothesisRegistry
from vinu_research.models import Hypothesis, HypothesisStatus
from vinu_research.signal_evidence_bridge import sync_signal_evidence_to_hypotheses
from vinu_research.storage.signal_evidence_store import SignalEvidenceStore


def _stores(tmp_path):
    evidence_store = SignalEvidenceStore(tmp_path / "signal_evidence.db")
    registry = HypothesisRegistry(tmp_path / "hypotheses.json")
    return evidence_store, registry


def _record_resolved_trigger(
    store: SignalEvidenceStore, trigger_id: str, symbol: str, condition: str,
    *, days_ago: int, return_at_horizon: float,
) -> None:
    trigger_time = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()
    store.record_trigger(trigger_id, symbol, trigger_time, condition, {})
    store.record_outcome(
        trigger_id, max_favorable_excursion=abs(return_at_horizon) + 0.01,
        max_adverse_excursion=-abs(return_at_horizon) - 0.01,
        return_at_horizon=return_at_horizon,
    )


class TestSyncUpdatesMatchingHypothesis:
    def test_appends_a_summary_evidence_entry(self, tmp_path):
        evidence_store, registry = _stores(tmp_path)
        h = Hypothesis.create("Momentum", "SMA cross thesis", universe=["AAPL"])
        h.signal_definition = "sma5_cross_sma50"
        registry.create(h)

        _record_resolved_trigger(evidence_store, "t1", "AAPL", "sma5_cross_sma50", days_ago=10, return_at_horizon=0.02)
        _record_resolved_trigger(evidence_store, "t2", "AAPL", "sma5_cross_sma50", days_ago=3, return_at_horizon=0.04)

        result = sync_signal_evidence_to_hypotheses(
            ["AAPL"], evidence_store=evidence_store, hypothesis_registry=registry,
        )

        assert result["updated"] == ["AAPL:sma5_cross_sma50"]
        assert result["no_matching_hypothesis"] == []
        assert result["no_resolved_triggers"] == []

        reloaded = registry.get(h.hypothesis_id)
        assert reloaded is not None
        assert len(reloaded.evidence) == 1
        ev = reloaded.evidence[0]
        assert ev.metric_kind == "signal_evidence"
        assert abs(ev.value - 0.03) < 1e-9  # avg of 0.02 and 0.04
        assert ev.conclusion == "supports"
        assert "2 historical trigger(s)" in ev.reasoning
        assert "100% positive" in ev.reasoning
        assert "3 day(s) ago" in ev.reasoning

    def test_does_not_touch_best_sharpe_or_auto_promote_status(self, tmp_path):
        evidence_store, registry = _stores(tmp_path)
        h = Hypothesis.create("Momentum", "SMA cross thesis", universe=["AAPL"])
        h.signal_definition = "sma5_cross_sma50"
        registry.create(h)
        _record_resolved_trigger(evidence_store, "t1", "AAPL", "sma5_cross_sma50", days_ago=1, return_at_horizon=0.9)

        sync_signal_evidence_to_hypotheses(["AAPL"], evidence_store=evidence_store, hypothesis_registry=registry)

        reloaded = registry.get(h.hypothesis_id)
        assert reloaded is not None
        assert reloaded.best_sharpe == 0.0
        assert reloaded.status == HypothesisStatus.exploring

    def test_negative_average_return_is_conclusion_contradicts(self, tmp_path):
        evidence_store, registry = _stores(tmp_path)
        h = Hypothesis.create("Momentum", "SMA cross thesis", universe=["AAPL"])
        h.signal_definition = "sma5_cross_sma50"
        registry.create(h)
        _record_resolved_trigger(evidence_store, "t1", "AAPL", "sma5_cross_sma50", days_ago=1, return_at_horizon=-0.05)

        sync_signal_evidence_to_hypotheses(["AAPL"], evidence_store=evidence_store, hypothesis_registry=registry)

        reloaded = registry.get(h.hypothesis_id)
        assert reloaded is not None
        assert reloaded.evidence[0].conclusion == "contradicts"

    def test_calling_twice_appends_a_second_entry_not_a_replace(self, tmp_path):
        """Evidence-trail semantics: each call adds to the history, it
        doesn't overwrite the previous summary -- the trail itself is
        the point."""
        evidence_store, registry = _stores(tmp_path)
        h = Hypothesis.create("Momentum", "SMA cross thesis", universe=["AAPL"])
        h.signal_definition = "sma5_cross_sma50"
        registry.create(h)
        _record_resolved_trigger(evidence_store, "t1", "AAPL", "sma5_cross_sma50", days_ago=1, return_at_horizon=0.02)

        sync_signal_evidence_to_hypotheses(["AAPL"], evidence_store=evidence_store, hypothesis_registry=registry)
        sync_signal_evidence_to_hypotheses(["AAPL"], evidence_store=evidence_store, hypothesis_registry=registry)

        reloaded = registry.get(h.hypothesis_id)
        assert reloaded is not None
        assert len(reloaded.evidence) == 2


class TestSyncSkipsRatherThanGuesses:
    def test_no_hypothesis_at_all_is_reported_not_auto_created(self, tmp_path):
        evidence_store, registry = _stores(tmp_path)
        _record_resolved_trigger(evidence_store, "t1", "AAPL", "sma5_cross_sma50", days_ago=1, return_at_horizon=0.02)

        result = sync_signal_evidence_to_hypotheses(
            ["AAPL"], evidence_store=evidence_store, hypothesis_registry=registry,
        )

        assert result["updated"] == []
        assert result["no_matching_hypothesis"] == ["AAPL"]
        assert registry.count() == 0  # confirms nothing was auto-created

    def test_hypothesis_with_a_different_signal_definition_does_not_match(self, tmp_path):
        evidence_store, registry = _stores(tmp_path)
        h = Hypothesis.create("Different thesis", "Not this condition", universe=["AAPL"])
        h.signal_definition = "rsi_oversold_bounce"
        registry.create(h)
        _record_resolved_trigger(evidence_store, "t1", "AAPL", "sma5_cross_sma50", days_ago=1, return_at_horizon=0.02)

        result = sync_signal_evidence_to_hypotheses(
            ["AAPL"], evidence_store=evidence_store, hypothesis_registry=registry,
        )

        assert result["updated"] == []
        assert result["no_matching_hypothesis"] == ["AAPL"]
        reloaded = registry.get(h.hypothesis_id)
        assert reloaded is not None
        assert reloaded.evidence == []

    def test_symbol_with_no_triggers_at_all(self, tmp_path):
        evidence_store, registry = _stores(tmp_path)
        result = sync_signal_evidence_to_hypotheses(
            ["AAPL"], evidence_store=evidence_store, hypothesis_registry=registry,
        )
        assert result == {"updated": [], "no_matching_hypothesis": [], "no_resolved_triggers": ["AAPL"]}

    def test_trigger_recorded_but_outcome_not_yet_resolved_is_not_summarized(self, tmp_path):
        """A still-open trigger (per SignalEvidenceStore's own docstring:
        outcome fields NULL until the recording horizon elapses) must not
        be treated as resolved evidence."""
        evidence_store, registry = _stores(tmp_path)
        h = Hypothesis.create("Momentum", "SMA cross thesis", universe=["AAPL"])
        h.signal_definition = "sma5_cross_sma50"
        registry.create(h)
        trigger_time = datetime.now(timezone.utc).isoformat()
        evidence_store.record_trigger("t1", "AAPL", trigger_time, "sma5_cross_sma50", {})

        result = sync_signal_evidence_to_hypotheses(
            ["AAPL"], evidence_store=evidence_store, hypothesis_registry=registry,
        )

        assert result["updated"] == []
        assert result["no_resolved_triggers"] == ["AAPL"]
        reloaded = registry.get(h.hypothesis_id)
        assert reloaded is not None
        assert reloaded.evidence == []


class TestSyncHandlesMultipleSymbolsIndependently:
    def test_one_symbols_failure_does_not_affect_another(self, tmp_path):
        evidence_store, registry = _stores(tmp_path)
        h = Hypothesis.create("AAPL momentum", "thesis", universe=["AAPL"])
        h.signal_definition = "sma5_cross_sma50"
        registry.create(h)
        _record_resolved_trigger(evidence_store, "t1", "AAPL", "sma5_cross_sma50", days_ago=1, return_at_horizon=0.02)
        # MSFT has triggers but no matching hypothesis at all.
        _record_resolved_trigger(evidence_store, "t2", "MSFT", "sma5_cross_sma50", days_ago=1, return_at_horizon=0.02)

        result = sync_signal_evidence_to_hypotheses(
            ["AAPL", "MSFT"], evidence_store=evidence_store, hypothesis_registry=registry,
        )

        assert result["updated"] == ["AAPL:sma5_cross_sma50"]
        assert result["no_matching_hypothesis"] == ["MSFT"]
