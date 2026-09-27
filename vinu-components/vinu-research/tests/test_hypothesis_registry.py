from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from vinu_research.hypothesis_registry import HypothesisRegistry
from vinu_research.models import Evidence, Hypothesis, HypothesisStatus


def _make_registry() -> tuple[HypothesisRegistry, Path]:
    tmp = tempfile.mkdtemp()
    path = Path(tmp) / "hypotheses.json"
    return HypothesisRegistry(path), path


class TestHypothesisModel:
    def test_create_generates_id(self):
        h = Hypothesis.create("Test", "Thesis about momentum")
        assert h.hypothesis_id.startswith("hyp_")
        assert len(h.hypothesis_id) == 16
        assert h.title == "Test"
        assert h.thesis == "Thesis about momentum"
        assert h.status == HypothesisStatus.exploring
        assert h.created_at != ""
        assert h.updated_at != ""

    def test_create_with_universe(self):
        h = Hypothesis.create("Test", "Thesis", universe=["AAPL", "MSFT"])
        assert h.universe == ["AAPL", "MSFT"]

    def test_create_defaults_source_to_system(self):
        h = Hypothesis.create("Test", "Thesis")
        assert h.source == "system"

    def test_create_from_human_always_tags_source_human(self):
        h = Hypothesis.create_from_human("Human Theory", "AAPL is due for a bounce", universe=["AAPL"])
        assert h.source == "human"
        assert h.title == "Human Theory"
        assert h.thesis == "AAPL is due for a bounce"

    def test_create_from_human_has_no_source_parameter_to_override(self):
        """Structural enforcement, not a convention: create_from_human's
        signature has no `source` parameter at all -- there is nothing a
        careless call site could pass to silently produce a
        non-"human"-tagged hypothesis through this path."""
        import inspect
        sig = inspect.signature(Hypothesis.create_from_human)
        assert "source" not in sig.parameters

    def test_source_persists_through_registry_round_trip(self):
        reg, _ = _make_registry()
        h = Hypothesis.create_from_human("Human Theory", "thesis text")
        reg.create(h)
        fetched = reg.get(h.hypothesis_id)
        assert fetched.source == "human"


class TestHypothesisRegistryCRUD:
    def test_create_and_get(self):
        reg, _ = _make_registry()
        h = Hypothesis.create("Momentum", "Momentum works in A-shares", universe=["AAPL"])
        saved = reg.create(h)
        assert saved.hypothesis_id == h.hypothesis_id

        loaded = reg.get(h.hypothesis_id)
        assert loaded is not None
        assert loaded.title == "Momentum"
        assert loaded.thesis == "Momentum works in A-shares"
        assert loaded.universe == ["AAPL"]
        assert loaded.status == HypothesisStatus.exploring

    def test_get_nonexistent(self):
        reg, _ = _make_registry()
        assert reg.get("hyp_nonexistent") is None

    def test_create_duplicate_raises(self):
        reg, _ = _make_registry()
        h = Hypothesis.create("Test", "Duplicate")
        reg.create(h)
        import pytest
        with pytest.raises(ValueError, match="already exists"):
            reg.create(h)

    def test_update(self):
        reg, _ = _make_registry()
        h = Hypothesis.create("Test", "Thesis")
        reg.create(h)
        h.status = HypothesisStatus.testing
        h.signal_definition = "rank(momentum_20d)"
        reg.update(h)
        loaded = reg.get(h.hypothesis_id)
        assert loaded is not None
        assert loaded.status == HypothesisStatus.testing
        assert loaded.signal_definition == "rank(momentum_20d)"

    def test_update_nonexistent_raises(self):
        reg, _ = _make_registry()
        h = Hypothesis.create("Test", "Nonexistent")
        import pytest
        with pytest.raises(KeyError, match="not found"):
            reg.update(h)

    def test_delete(self):
        reg, _ = _make_registry()
        h = Hypothesis.create("Test", "To delete")
        reg.create(h)
        assert reg.delete(h.hypothesis_id) is True
        assert reg.get(h.hypothesis_id) is None

    def test_delete_nonexistent(self):
        reg, _ = _make_registry()
        assert reg.delete("hyp_nonexistent") is False

    def test_list_all(self):
        reg, _ = _make_registry()
        h1 = Hypothesis.create("Alpha", "Alpha strategy")
        h2 = Hypothesis.create("Beta", "Beta strategy")
        reg.create(h1)
        reg.create(h2)
        all_h = reg.list_all()
        assert len(all_h) == 2

    def test_list_all_filter_by_status(self):
        reg, _ = _make_registry()
        h1 = Hypothesis.create("Exploring", "E")
        h2 = Hypothesis.create("Validated", "V")
        reg.create(h1)
        h2.status = HypothesisStatus.validated
        reg.create(h2)
        exploring = reg.list_all(status=HypothesisStatus.exploring)
        assert len(exploring) == 1
        assert exploring[0].title == "Exploring"


class TestHypothesisBacktestLinking:
    def test_link_backtest(self):
        reg, _ = _make_registry()
        h = Hypothesis.create("Test", "Thesis")
        reg.create(h)
        result = reg.link_backtest(h.hypothesis_id, "/tmp/run_card.json")
        assert result is not None
        assert "/tmp/run_card.json" in result.run_cards

    def test_link_backtest_nonexistent(self):
        reg, _ = _make_registry()
        result = reg.link_backtest("hyp_nonexistent", "/tmp/run_card.json")
        assert result is None

    def test_link_backtest_idempotent(self):
        reg, _ = _make_registry()
        h = Hypothesis.create("Test", "Thesis")
        reg.create(h)
        reg.link_backtest(h.hypothesis_id, "/tmp/run_card.json")
        reg.link_backtest(h.hypothesis_id, "/tmp/run_card.json")
        loaded = reg.get(h.hypothesis_id)
        assert loaded is not None
        assert loaded.run_cards == ["/tmp/run_card.json"]


class TestAddEvidenceBatch:
    def test_add_evidence_batch_updates_all_hypotheses(self):
        reg, _ = _make_registry()
        h1 = Hypothesis.create("Momentum", "Momentum strategy", universe=["AAPL"])
        h2 = Hypothesis.create("MeanRev", "Mean reversion strategy", universe=["MSFT"])
        reg.create(h1)
        reg.create(h2)

        ev1 = Evidence(run_id=1, iteration=1, metric="sharpe", value=0.6, conclusion="supports", reasoning="good returns")
        ev2 = Evidence(run_id=1, iteration=2, metric="sharpe", value=0.4, conclusion="contradicts", reasoning="faded")
        evidence_map = {
            h1.hypothesis_id: [ev1],
            h2.hypothesis_id: [ev1, ev2],
        }
        for hid, ev_list in evidence_map.items():
            reg.add_evidence_batch(hid, ev_list)

        loaded1 = reg.get(h1.hypothesis_id)
        loaded2 = reg.get(h2.hypothesis_id)
        assert loaded1 is not None
        assert loaded2 is not None
        assert len(loaded1.evidence) == 1
        assert loaded1.evidence[0].value == 0.6
        assert len(loaded2.evidence) == 2
        assert loaded2.evidence[1].conclusion == "contradicts"

    def test_add_evidence_batch_updates_best_sharpe(self):
        reg, _ = _make_registry()
        h = Hypothesis.create("Test", "Test", universe=["AAPL"])
        reg.create(h)

        evs = [
            Evidence(run_id=1, iteration=1, metric="sharpe", value=0.3, conclusion="supports", reasoning="ok"),
            Evidence(run_id=2, iteration=2, metric="sharpe", value=0.8, conclusion="supports", reasoning="better"),
            Evidence(run_id=3, iteration=3, metric="sharpe", value=0.5, conclusion="supports", reasoning="medium"),
        ]
        reg.add_evidence_batch(h.hypothesis_id, evs)
        loaded = reg.get(h.hypothesis_id)
        assert loaded is not None
        assert loaded.best_sharpe == 0.8

    def test_add_evidence_batch_nonexistent_returns_none(self):
        reg, _ = _make_registry()
        result = reg.add_evidence_batch("hyp_nonexistent", [])
        assert result is None


class TestMetricKindGatesPromotion:
    """item #1: add_evidence()'s best_sharpe/status promotion math is
    Sharpe-specific (0.3/0.5 thresholds, best_sharpe = max seen value) --
    a non-Sharpe evidence kind (e.g. an average forward return) must not
    silently corrupt best_sharpe or auto-promote status just because its
    raw number happens to cross the same literal threshold."""

    def test_default_metric_kind_is_sharpe_existing_behavior_unchanged(self):
        ev = Evidence(run_id=1, iteration=1, metric="sharpe", value=0.6, conclusion="supports", reasoning="x")
        assert ev.metric_kind == "sharpe"

    def test_non_sharpe_evidence_is_appended_but_does_not_touch_best_sharpe(self):
        reg, _ = _make_registry()
        h = Hypothesis.create("Test", "Test", universe=["AAPL"])
        reg.create(h)
        ev = Evidence(
            run_id="signal_evidence", iteration=0, metric="avg_return_at_horizon",
            value=0.4, conclusion="supports", reasoning="looks strong",
            metric_kind="signal_evidence",
        )
        result = reg.add_evidence(h.hypothesis_id, ev)
        assert result is not None
        assert len(result.evidence) == 1
        assert result.evidence[0].value == 0.4
        assert result.best_sharpe == 0.0

    def test_non_sharpe_evidence_never_auto_promotes_status(self):
        reg, _ = _make_registry()
        h = Hypothesis.create("Test", "Test", universe=["AAPL"])
        reg.create(h)
        ev = Evidence(
            run_id="signal_evidence", iteration=0, metric="avg_return_at_horizon",
            value=0.9, conclusion="supports", reasoning="way above 0.5",
            metric_kind="signal_evidence",
        )
        result = reg.add_evidence(h.hypothesis_id, ev)
        assert result is not None
        assert result.status == HypothesisStatus.exploring

    def test_sharpe_evidence_still_promotes_exactly_as_before(self):
        """Regression guard for the fix itself -- confirms gating on
        metric_kind didn't quietly disable the real, existing promotion
        path for actual Sharpe-based evidence."""
        reg, _ = _make_registry()
        h = Hypothesis.create("Test", "Test", universe=["AAPL"])
        reg.create(h)
        ev = Evidence(run_id=1, iteration=1, metric="sharpe", value=0.6, conclusion="supports", reasoning="x")
        result = reg.add_evidence(h.hypothesis_id, ev)
        assert result is not None
        assert result.best_sharpe == 0.6
        assert result.status == HypothesisStatus.validated

    def test_mixed_batch_only_sharpe_entries_affect_promotion(self):
        reg, _ = _make_registry()
        h = Hypothesis.create("Test", "Test", universe=["AAPL"])
        reg.create(h)
        evs = [
            Evidence(
                run_id="signal_evidence", iteration=0, metric="avg_return_at_horizon",
                value=0.95, conclusion="supports", reasoning="signal evidence, ignored",
                metric_kind="signal_evidence",
            ),
            Evidence(run_id=1, iteration=1, metric="sharpe", value=0.4, conclusion="supports", reasoning="real sharpe"),
        ]
        result = reg.add_evidence_batch(h.hypothesis_id, evs)
        assert result is not None
        assert result.best_sharpe == 0.4
        assert len(result.evidence) == 2

    def test_metric_kind_round_trips_through_persistence(self):
        reg, _ = _make_registry()
        h = Hypothesis.create("Test", "Test", universe=["AAPL"])
        reg.create(h)
        ev = Evidence(
            run_id="signal_evidence", iteration=0, metric="avg_return_at_horizon",
            value=0.1, conclusion="supports", reasoning="x", metric_kind="signal_evidence",
        )
        reg.add_evidence(h.hypothesis_id, ev)
        reloaded = reg.get(h.hypothesis_id)
        assert reloaded is not None
        assert reloaded.evidence[0].metric_kind == "signal_evidence"
        assert reloaded.evidence[0].run_id == "signal_evidence"

    def test_pre_existing_persisted_evidence_with_no_metric_kind_column_defaults_to_sharpe(self):
        """A hypothesis JSON file written before this field existed has no
        `metric_kind` key at all on its evidence rows -- must load as
        "sharpe" (accurate: every pre-existing row really is Sharpe-based),
        not crash or silently become a non-promoting kind."""
        reg, path = _make_registry()
        h = Hypothesis.create("Test", "Test", universe=["AAPL"])
        reg.create(h)
        data = json.loads(path.read_text())
        data["hypotheses"][h.hypothesis_id]["evidence"] = [
            {
                "run_id": 1, "iteration": 1, "metric": "sharpe", "value": 0.6,
                "conclusion": "supports", "reasoning": "old row, no metric_kind key",
            }
        ]
        path.write_text(json.dumps(data))
        reloaded = reg.get(h.hypothesis_id)
        assert reloaded is not None
        assert reloaded.evidence[0].metric_kind == "sharpe"


class TestPoolEvidenceByIndicator:
    """item #8: does a supporting indicator matter in general, across every
    strategy that used it, not siloed per-strategy."""

    def test_pools_evidence_from_multiple_hypotheses_sharing_an_indicator(self):
        reg, _ = _make_registry()
        h1 = Hypothesis.create("Momentum", "Momentum strategy", universe=["AAPL"])
        h1.indicators_used = ["adx_gt_25", "rsi_14"]
        h2 = Hypothesis.create("Breakout", "Breakout strategy", universe=["MSFT"])
        h2.indicators_used = ["adx_gt_25"]
        reg.create(h1)
        reg.create(h2)
        reg.add_evidence_batch(h1.hypothesis_id, [
            Evidence(run_id=1, iteration=1, metric="sharpe", value=0.6, conclusion="supports", reasoning="r"),
        ])
        reg.add_evidence_batch(h2.hypothesis_id, [
            Evidence(run_id=1, iteration=1, metric="sharpe", value=0.2, conclusion="contradicts", reasoning="r"),
        ])

        pools = reg.pool_evidence_by_indicator()
        adx = pools["adx_gt_25"]["sharpe"]
        assert adx["evidence_count"] == 2
        assert adx["hypothesis_count"] == 2
        assert adx["avg_value"] == pytest.approx(0.4)
        assert adx["support_rate"] == pytest.approx(0.5)

        rsi = pools["rsi_14"]["sharpe"]
        assert rsi["evidence_count"] == 1
        assert rsi["hypothesis_count"] == 1

    def test_does_not_mix_metric_kinds_under_one_number(self):
        reg, _ = _make_registry()
        h = Hypothesis.create("Mixed", "Mixed evidence kinds", universe=["AAPL"])
        h.indicators_used = ["adx_gt_25"]
        reg.create(h)
        reg.add_evidence_batch(h.hypothesis_id, [
            Evidence(run_id=1, iteration=1, metric="sharpe", value=0.6, conclusion="supports", reasoning="r"),
            Evidence(run_id="se_1", iteration=0, metric="avg_return", value=30.0,
                     conclusion="supports", reasoning="r", metric_kind="signal_evidence"),
        ])

        pools = reg.pool_evidence_by_indicator()
        by_kind = pools["adx_gt_25"]
        assert set(by_kind.keys()) == {"sharpe", "signal_evidence"}
        assert by_kind["sharpe"]["avg_value"] == pytest.approx(0.6)
        assert by_kind["signal_evidence"]["avg_value"] == pytest.approx(30.0)

    def test_hypothesis_with_no_indicators_used_contributes_nothing(self):
        reg, _ = _make_registry()
        h = Hypothesis.create("NoIndicators", "No indicators tagged", universe=["AAPL"])
        reg.create(h)
        reg.add_evidence_batch(h.hypothesis_id, [
            Evidence(run_id=1, iteration=1, metric="sharpe", value=0.6, conclusion="supports", reasoning="r"),
        ])
        assert reg.pool_evidence_by_indicator() == {}

    def test_hypothesis_with_no_evidence_contributes_nothing(self):
        reg, _ = _make_registry()
        h = Hypothesis.create("NoEvidence", "Tagged but untested", universe=["AAPL"])
        h.indicators_used = ["adx_gt_25"]
        reg.create(h)
        assert reg.pool_evidence_by_indicator() == {}

    def test_empty_registry_returns_empty_dict(self):
        reg, _ = _make_registry()
        assert reg.pool_evidence_by_indicator() == {}


class TestHypothesisSearch:
    def test_search_by_title(self):
        reg, _ = _make_registry()
        h = Hypothesis.create("Momentum Decay", "Testing momentum decay in low vol")
        reg.create(h)
        results = reg.search("momentum")
        assert len(results) >= 1
        assert results[0].title == "Momentum Decay"

    def test_search_by_thesis(self):
        reg, _ = _make_registry()
        h = Hypothesis.create("Test", "Mean reversion in small caps")
        reg.create(h)
        results = reg.search("small caps")
        assert len(results) >= 1

    def test_search_no_match(self):
        reg, _ = _make_registry()
        results = reg.search("zzzzz_nonexistent")
        assert len(results) == 0


class TestHypothesisPersistence:
    def test_persists_across_registry_instances(self):
        tmp = tempfile.mkdtemp()
        path = Path(tmp) / "hypotheses.json"
        reg1 = HypothesisRegistry(path)
        h = Hypothesis.create("Persist", "Data should survive")
        reg1.create(h)

        reg2 = HypothesisRegistry(path)
        loaded = reg2.get(h.hypothesis_id)
        assert loaded is not None
        assert loaded.title == "Persist"

    def test_atomic_write_does_not_corrupt_on_partial_write(self):
        tmp = tempfile.mkdtemp()
        path = Path(tmp) / "hypotheses.json"
        reg = HypothesisRegistry(path)
        h = Hypothesis.create("Atomic", "Test")
        reg.create(h)
        content = path.read_text(encoding="utf-8")
        data = json.loads(content)
        assert "hypotheses" in data
        assert h.hypothesis_id in data["hypotheses"]

    def test_count(self):
        reg, _ = _make_registry()
        assert reg.count() == 0
        reg.create(Hypothesis.create("A", "A"))
        reg.create(Hypothesis.create("B", "B"))
        assert reg.count() == 2
