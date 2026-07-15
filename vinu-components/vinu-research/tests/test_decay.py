from __future__ import annotations

import tempfile
from pathlib import Path

from vinu_research.config import DecayThresholds
from vinu_research.decay import (
    compute_decay_metrics,
    compute_decay_snapshot,
    evaluate_health,
    transition_status,
)
from vinu_research.models import Artifact, ArtifactStatus, BenchEntry, DecaySnapshot
from vinu_research.storage.strategy_store import SqliteStrategyStore


class TestArtifactModel:
    def test_create_generates_id(self):
        a = Artifact.create("STRATEGY", "Momentum Strategy", universe=["AAPL"])
        assert a.artifact_id.startswith("art_")
        assert a.type == "STRATEGY"
        assert a.name == "Momentum Strategy"
        assert a.universe == ["AAPL"]
        assert a.status == ArtifactStatus.CREATED
        assert a.created_at != ""
        assert a.updated_at != ""

    def test_create_default_universe(self):
        a = Artifact.create("FACTOR", "Alpha Factor")
        assert a.universe == []


class TestDecayMetrics:
    def test_healthy_metrics(self):
        entries = [
            BenchEntry(artifact_id="test", date=f"2024-01-{d:02d}",
                       ic=0.05 + d * 0.001, ir=0.5 + d * 0.02,
                       ic_positive=True, sharpe=1.5 + d * 0.02)
            for d in range(1, 21)
        ]
        metrics = compute_decay_metrics(entries)
        assert metrics["ic_ratio"] > 0.9
        assert metrics["rolling_ir"] > 0
        assert metrics["ic_positive_ratio"] >= 0.9
        assert metrics["rolling_sharpe"] > 1.0
        assert metrics["n_entries"] == 20

    def test_decayed_metrics(self):
        entries = [
            BenchEntry(artifact_id="test", date=f"2024-01-{d:02d}",
                       ic=0.05 - d * 0.003, ir=0.5 - d * 0.03,
                       ic_positive=d <= 10, sharpe=1.5 - d * 0.1)
            for d in range(1, 21)
        ]
        metrics = compute_decay_metrics(entries)
        assert metrics["ic_ratio"] < 0.7
        assert metrics["ic_positive_ratio"] <= 0.5
        assert metrics["rolling_sharpe"] < 0.5

    def test_insufficient_entries(self):
        metrics = compute_decay_metrics([])
        assert metrics["n_entries"] == 0

        metrics = compute_decay_metrics([
            BenchEntry(artifact_id="test", date="2024-01-01",
                       ic=0.05, ir=0.5, ic_positive=True, sharpe=1.0),
        ])
        assert metrics["n_entries"] == 1
        assert metrics["ic_ratio"] == 0.0


class TestEvaluateHealth:
    def test_healthy(self):
        metrics = {
            "ic_ratio": 0.85,
            "rolling_ir": 1.5,
            "ic_positive_ratio": 0.7,
            "rolling_sharpe": 1.2,
        }
        assert evaluate_health(metrics) == "HEALTHY"

    def test_warning(self):
        metrics = {
            "ic_ratio": 0.6,
            "rolling_ir": 0.7,
            "ic_positive_ratio": 0.5,
            "rolling_sharpe": 0.6,
        }
        assert evaluate_health(metrics) == "WARNING"

    def test_decayed(self):
        metrics = {
            "ic_ratio": 0.4,
            "rolling_ir": 0.3,
            "ic_positive_ratio": 0.4,
            "rolling_sharpe": 0.3,
        }
        assert evaluate_health(metrics) == "DECAYED"

    def test_critical(self):
        metrics = {
            "ic_ratio": 0.1,
            "rolling_ir": 0.0,
            "ic_positive_ratio": 0.3,
            "rolling_sharpe": -0.2,
        }
        assert evaluate_health(metrics) == "CRITICAL"

    def test_custom_thresholds(self):
        strict = DecayThresholds(
            ic_ratio_healthy=0.9,
            ir_healthy=2.0,
        )
        metrics = {
            "ic_ratio": 0.85,
            "rolling_ir": 1.5,
            "ic_positive_ratio": 0.7,
            "rolling_sharpe": 1.2,
        }
        assert evaluate_health(metrics, strict) == "WARNING"


class TestTransitionStatus:
    def test_active_to_monitoring_after_3_warnings(self):
        result = transition_status(
            ArtifactStatus.ACTIVE,
            ["HEALTHY", "WARNING", "WARNING", "WARNING"],
        )
        assert result == ArtifactStatus.MONITORING

    def test_active_stays_active_with_less_than_3_warnings(self):
        result = transition_status(
            ArtifactStatus.ACTIVE,
            ["HEALTHY", "WARNING", "HEALTHY"],
        )
        assert result == ArtifactStatus.ACTIVE

    def test_monitoring_to_active_on_healthy(self):
        result = transition_status(
            ArtifactStatus.MONITORING,
            ["WARNING", "HEALTHY"],
        )
        assert result == ArtifactStatus.ACTIVE

    def test_monitoring_to_decayed_after_2_decayed(self):
        result = transition_status(
            ArtifactStatus.MONITORING,
            ["WARNING", "DECAYED", "DECAYED"],
        )
        assert result == ArtifactStatus.DECAYED

    def test_decayed_to_disabled_after_3_critical(self):
        result = transition_status(
            ArtifactStatus.DECAYED,
            ["CRITICAL", "CRITICAL", "CRITICAL"],
        )
        assert result == ArtifactStatus.DISABLED

    def test_no_transition_with_empty_history(self):
        result = transition_status(ArtifactStatus.ACTIVE, [])
        assert result == ArtifactStatus.ACTIVE

    def test_decayed_stays_decayed_with_mixed_signals(self):
        result = transition_status(
            ArtifactStatus.DECAYED,
            ["CRITICAL", "HEALTHY", "CRITICAL"],
        )
        assert result == ArtifactStatus.DECAYED


class TestDecaySnapshot:
    def test_compute_snapshot(self):
        entries = [
            BenchEntry(artifact_id="a1", date=f"2024-01-{d:02d}",
                       ic=0.05, ir=0.5, ic_positive=True, sharpe=1.2)
            for d in range(1, 11)
        ]
        snap = compute_decay_snapshot("a1", entries)
        assert snap.artifact_id == "a1"
        assert snap.evaluation in ("HEALTHY", "WARNING", "DECAYED", "CRITICAL")
        assert snap.n_entries == 10
        assert snap.timestamp != ""


class TestSqliteStrategyStore:
    @staticmethod
    def _make_store() -> tuple[SqliteStrategyStore, Path]:
        tmp = tempfile.mkdtemp()
        path = Path(tmp) / "strategy_store.db"
        return SqliteStrategyStore(path), path

    def test_upsert_and_get_artifact(self):
        store, _ = self._make_store()
        a = Artifact.create("STRATEGY", "Test Strategy")
        store.upsert_artifact(a)
        loaded = store.get_artifact(a.artifact_id)
        assert loaded is not None
        assert loaded.name == "Test Strategy"
        assert loaded.status == ArtifactStatus.CREATED

    def test_list_artifacts_by_status(self):
        store, _ = self._make_store()
        a1 = Artifact.create("STRATEGY", "Active")
        a1.status = ArtifactStatus.ACTIVE
        a2 = Artifact.create("STRATEGY", "Monitoring")
        a2.status = ArtifactStatus.MONITORING
        store.upsert_artifact(a1)
        store.upsert_artifact(a2)
        active = store.list_artifacts(status=ArtifactStatus.ACTIVE)
        assert len(active) == 1
        assert active[0].name == "Active"

    def test_list_artifacts_by_type(self):
        store, _ = self._make_store()
        store.upsert_artifact(Artifact.create("STRATEGY", "S1"))
        store.upsert_artifact(Artifact.create("FACTOR", "F1"))
        strategies = store.list_artifacts(type_="STRATEGY")
        assert len(strategies) == 1

    def test_delete_artifact(self):
        store, _ = self._make_store()
        a = Artifact.create("STRATEGY", "To Delete")
        store.upsert_artifact(a)
        assert store.delete_artifact(a.artifact_id) is True
        assert store.get_artifact(a.artifact_id) is None

    def test_append_and_get_bench_history(self):
        store, _ = self._make_store()
        a = Artifact.create("STRATEGY", "Bench Test")
        store.upsert_artifact(a)
        entry = BenchEntry(artifact_id=a.artifact_id, date="2024-01-01",
                           ic=0.05, ir=0.5, ic_positive=True, sharpe=1.2)
        store.append_bench_entry(entry)
        history = store.get_bench_history(a.artifact_id)
        assert len(history) == 1
        assert history[0].ic == 0.05

    def test_save_and_get_snapshots(self):
        store, _ = self._make_store()
        a = Artifact.create("STRATEGY", "Snapshot Test")
        store.upsert_artifact(a)
        snap = DecaySnapshot(
            artifact_id=a.artifact_id,
            evaluation="HEALTHY",
            ic_ratio=0.8,
            rolling_ir=1.2,
            ic_positive_ratio=0.6,
            rolling_sharpe=1.0,
            n_entries=10,
            timestamp="2024-01-01T00:00:00",
        )
        store.save_snapshot(snap)
        latest = store.get_latest_snapshot(a.artifact_id)
        assert latest is not None
        assert latest.evaluation == "HEALTHY"

    def test_full_decay_scan_workflow(self):
        store, _ = self._make_store()
        a = Artifact.create("STRATEGY", "Decay Workflow")
        a.status = ArtifactStatus.ACTIVE
        store.upsert_artifact(a)

        for d in range(1, 11):
            entry = BenchEntry(
                artifact_id=a.artifact_id,
                date=f"2024-01-{d:02d}",
                ic=0.01,
                ir=0.1,
                ic_positive=False,
                sharpe=0.2,
            )
            store.append_bench_entry(entry)

        history = store.get_bench_history(a.artifact_id)
        from vinu_research.decay import compute_decay_snapshot
        snap = compute_decay_snapshot(a.artifact_id, history)
        store.save_snapshot(snap)

        previous = store.get_snapshots(a.artifact_id)
        eval_history = [s.evaluation for s in previous]
        new_status = transition_status(a.status, eval_history)

        assert new_status in (ArtifactStatus.ACTIVE, ArtifactStatus.MONITORING)
