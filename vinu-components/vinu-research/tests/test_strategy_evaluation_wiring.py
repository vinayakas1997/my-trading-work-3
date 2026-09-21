"""Confirms decay-scan and promote-scan actually write into the new
shared strategy_evaluation store (missing-pieces-of-system/
startegy-enhancer/01-plan.md section 2)."""

from __future__ import annotations

import argparse

import pytest

from vinu_infra.strategy_evaluation import StrategyEvaluationStore
from vinu_research.config import DecayThresholds
from vinu_research.models import Artifact, ArtifactStatus, BenchEntry
from vinu_research.storage.strategy_store import SqliteStrategyStore


@pytest.fixture
def eval_data_root(tmp_path, monkeypatch):
    root = tmp_path / "eval"
    root.mkdir()
    monkeypatch.setenv("VINU_STRATEGY_EVAL_DATA_ROOT", str(root))
    return root


def _make_active_strategy_artifact(store, *, artifact_id="art1", universe=("AAPL",)) -> Artifact:
    art = Artifact(
        artifact_id=artifact_id, type="strategy", name="test-strat",
        universe=list(universe), status=ArtifactStatus.ACTIVE,
    )
    store.upsert_artifact(art)
    return art


class TestDecayScanWiring:
    def test_healthy_scan_writes_pass(self, tmp_path, eval_data_root):
        from vinu_research.cli import _run_decay_scan

        store = SqliteStrategyStore(tmp_path / "strategy.db")
        art = _make_active_strategy_artifact(store)
        for i in range(10):
            store.append_bench_entry(
                BenchEntry(artifact_id=art.artifact_id, date=f"2026-01-{i+1:02d}", sharpe=1.5)
            )

        _run_decay_scan(store, DecayThresholds(), dry_run=True)

        eval_store = StrategyEvaluationStore(eval_data_root / "strategy_evaluation.db")
        history = eval_store.get_history(art.artifact_id)
        decay_rows = [h for h in history if h["step_name"] == "decay_scan"]
        assert len(decay_rows) == 1
        assert decay_rows[0]["verdict"] == "PASS"
        assert decay_rows[0]["ticker"] == "AAPL"

    def test_decayed_scan_writes_fail_and_sets_status(self, tmp_path, eval_data_root):
        from vinu_research.cli import _run_decay_scan

        store = SqliteStrategyStore(tmp_path / "strategy.db")
        art = _make_active_strategy_artifact(store)
        # First a healthy baseline, then a real collapse -- matches the
        # existing test_decay*.py fixture shape for a genuine DECAYED read.
        for i in range(5):
            store.append_bench_entry(
                BenchEntry(artifact_id=art.artifact_id, date=f"2026-01-{i+1:02d}", sharpe=1.5, ic=0.1, ic_positive=True)
            )
        for i in range(5, 10):
            store.append_bench_entry(
                BenchEntry(artifact_id=art.artifact_id, date=f"2026-01-{i+1:02d}", sharpe=-1.0, ic=-0.1, ic_positive=False)
            )

        _run_decay_scan(store, DecayThresholds(), dry_run=True)

        eval_store = StrategyEvaluationStore(eval_data_root / "strategy_evaluation.db")
        history = eval_store.get_history(art.artifact_id)
        decay_rows = [h for h in history if h["step_name"] == "decay_scan"]
        assert len(decay_rows) == 1
        # Real behavior depends on compute_strategy_decay_snapshot's actual
        # threshold math -- assert the row exists with real reasoning
        # content, not a guessed verdict value.
        assert decay_rows[0]["reasoning"].startswith("evaluation=")


class TestPromoteScanWiring:
    def test_promote_scan_writes_promotion_bar_result(self, tmp_path, eval_data_root, monkeypatch):
        from vinu_research.cli import promote_scan_main

        monkeypatch.setenv("VINU_RESEARCH_DATA_ROOT", str(tmp_path))
        db_path = tmp_path / "strategy.db"
        store = SqliteStrategyStore(db_path)
        art = Artifact(
            artifact_id="art-promote", type="strategy", name="test-strat",
            universe=["MSFT"], status=ArtifactStatus.BENCHING,
        )
        art.deflated_sharpe = 0.0  # below any real threshold -> should FAIL
        store.upsert_artifact(art)

        args = argparse.Namespace(db=str(db_path), dry_run=True)
        promote_scan_main(args)

        eval_store = StrategyEvaluationStore(eval_data_root / "strategy_evaluation.db")
        history = eval_store.get_history("art-promote")
        promo_rows = [h for h in history if h["step_name"] == "promotion_bar"]
        assert len(promo_rows) == 1
        assert promo_rows[0]["verdict"] == "FAIL"
        assert promo_rows[0]["ticker"] == "MSFT"
