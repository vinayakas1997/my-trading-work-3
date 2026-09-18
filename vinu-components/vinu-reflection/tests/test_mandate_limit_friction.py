"""Tests for analysis O (Governance & Freshness) -- are operator mandate
limits protecting against real risk, or just friction. See
missing-pieces-of-system/maturity-agentic-system/thinking-1/02-decided-pattern/
25-A-Y-details/05-governance-freshness.md.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vinu_infra.reflection import ReflectionStore, write_findings
from vinu_research.models import Artifact, DecaySnapshot
from vinu_research.storage.strategy_store import SqliteStrategyStore

from vinu_reflection.reflection import mandate_limit_friction


@pytest.fixture
def data_root(tmp_path, monkeypatch) -> Path:
    # mandate_limit_friction.run() reads the strategy store via
    # get_strategy_store() (VINU_RESEARCH_DATA_ROOT), same as B/V --
    # data_root_paths has no "vinu_research" key in the real wiring.
    monkeypatch.setenv("VINU_RESEARCH_DATA_ROOT", str(tmp_path))
    return tmp_path


def _seed_rejection(log_path: Path, *, symbol: str, artifact_ids: list[str]) -> None:
    entry = {
        "id": "x", "action": "order_rejected", "symbol": symbol,
        "details": {"blocked_artifact_ids": artifact_ids}, "timestamp": "2026-01-01T00:00:00Z",
    }
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def _seed_artifact_with_snapshot(store: SqliteStrategyStore, *, artifact_id: str, symbol: str, evaluation: str) -> None:
    artifact = Artifact.create("strategy", "test", universe=[symbol])
    artifact.artifact_id = artifact_id
    store.upsert_artifact(artifact)
    store.save_snapshot(DecaySnapshot(artifact_id=artifact_id, evaluation=evaluation, timestamp="2026-01-01T00:00:00Z"))


class TestMandateLimitFrictionRun:
    def test_no_data_returns_no_findings(self, data_root):
        SqliteStrategyStore(data_root / "strategy_store.db")
        findings = mandate_limit_friction.run({"vinu_agent": data_root})
        assert findings == []

    def test_below_evidence_minimum_is_skipped(self, data_root):
        store = SqliteStrategyStore(data_root / "strategy_store.db")
        log_path = data_root / "trade_audit.log"
        for i in range(3):
            aid = f"art-{i}"
            _seed_artifact_with_snapshot(store, artifact_id=aid, symbol="AAPL", evaluation="HEALTHY")
            _seed_rejection(log_path, symbol="AAPL", artifact_ids=[aid])

        findings = mandate_limit_friction.run({"vinu_agent": data_root})
        assert findings == []

    def test_rejections_with_no_blocked_artifact_ids_are_ignored(self, data_root):
        SqliteStrategyStore(data_root / "strategy_store.db")
        log_path = data_root / "trade_audit.log"
        for i in range(15):
            entry = {"action": "order_rejected", "symbol": "AAPL", "details": {}}
            with log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")

        findings = mandate_limit_friction.run({"vinu_agent": data_root})
        assert findings == []

    def test_untrackable_artifact_no_snapshot_is_skipped(self, data_root):
        store = SqliteStrategyStore(data_root / "strategy_store.db")
        log_path = data_root / "trade_audit.log"
        for i in range(15):
            aid = f"art-{i}"
            artifact = Artifact.create("strategy", "test", universe=["AAPL"])
            artifact.artifact_id = aid
            store.upsert_artifact(artifact)
            # no decay snapshot saved -- not trackable
            _seed_rejection(log_path, symbol="AAPL", artifact_ids=[aid])

        findings = mandate_limit_friction.run({"vinu_agent": data_root})
        assert findings == []

    def test_finds_symbol_with_healthier_blocked_artifacts_than_system(self, data_root):
        store = SqliteStrategyStore(data_root / "strategy_store.db")
        log_path = data_root / "trade_audit.log"

        # AAPL: 10 blocked artifacts, all HEALTHY (limit looks like friction).
        for i in range(10):
            aid = f"aapl-art-{i}"
            _seed_artifact_with_snapshot(store, artifact_id=aid, symbol="AAPL", evaluation="HEALTHY")
            _seed_rejection(log_path, symbol="AAPL", artifact_ids=[aid])
        # MSFT: 10 blocked artifacts, all DECAYED (limit looks protective).
        for i in range(10):
            aid = f"msft-art-{i}"
            _seed_artifact_with_snapshot(store, artifact_id=aid, symbol="MSFT", evaluation="DECAYED")
            _seed_rejection(log_path, symbol="MSFT", artifact_ids=[aid])

        findings = mandate_limit_friction.run({"vinu_agent": data_root})
        by_scope = {f.scope_key: f for f in findings}
        assert "AAPL" in by_scope
        finding = by_scope["AAPL"]
        assert finding.analyst_name == "mandate_limit_friction"
        assert finding.scope_type == "ticker"
        assert finding.evidence_count == 10
        assert finding.signal_json["projected_performance_of_blocked"] == pytest.approx(1.0)
        assert finding.signal_json["system_healthy_fraction"] == pytest.approx(0.5)

    def test_same_artifact_rejected_repeatedly_counted_once(self, data_root):
        store = SqliteStrategyStore(data_root / "strategy_store.db")
        log_path = data_root / "trade_audit.log"
        aid = "aapl-art-1"
        _seed_artifact_with_snapshot(store, artifact_id=aid, symbol="AAPL", evaluation="HEALTHY")
        for _ in range(15):
            _seed_rejection(log_path, symbol="AAPL", artifact_ids=[aid])

        findings = mandate_limit_friction.run({"vinu_agent": data_root})
        assert findings == []  # only 1 real evidence point despite 15 rejections


class TestMandateLimitFrictionEndToEnd:
    def test_run_write_findings_round_trip(self, data_root):
        store = SqliteStrategyStore(data_root / "strategy_store.db")
        log_path = data_root / "trade_audit.log"
        reflection_store = ReflectionStore(data_root / "reflection.db")
        mandate_limit_friction.seed_reference_config(reflection_store)

        for i in range(10):
            aid = f"aapl-art-{i}"
            _seed_artifact_with_snapshot(store, artifact_id=aid, symbol="AAPL", evaluation="HEALTHY")
            _seed_rejection(log_path, symbol="AAPL", artifact_ids=[aid])
        for i in range(10):
            aid = f"msft-art-{i}"
            _seed_artifact_with_snapshot(store, artifact_id=aid, symbol="MSFT", evaluation="DECAYED")
            _seed_rejection(log_path, symbol="MSFT", artifact_ids=[aid])

        findings = mandate_limit_friction.run({"vinu_agent": data_root})
        written = write_findings(reflection_store, findings)
        assert len(written) >= 1
