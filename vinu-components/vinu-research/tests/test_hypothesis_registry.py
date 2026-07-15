from __future__ import annotations

import json
import tempfile
from pathlib import Path

from vinu_research.hypothesis_registry import HypothesisRegistry
from vinu_research.models import Hypothesis, HypothesisStatus


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
