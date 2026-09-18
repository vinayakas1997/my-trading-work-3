"""Tests for analysis B (regime x strategy coverage map)."""

from __future__ import annotations

from pathlib import Path

import pytest

from vinu_infra.trade_audit_log import record_exit
from vinu_research.models import Artifact

from vinu_reflection.reflection import regime_strategy_coverage


@pytest.fixture
def data_root(tmp_path) -> Path:
    return tmp_path


@pytest.fixture
def strategy_store(tmp_path, monkeypatch):
    research_root = tmp_path / "research"
    research_root.mkdir()
    monkeypatch.setenv("VINU_RESEARCH_DATA_ROOT", str(research_root))
    return regime_strategy_coverage.get_strategy_store()


def _log_path(data_root: Path) -> Path:
    return data_root / "vinu_live" / "trade_audit_log.jsonl"


def _seed_trades(
    strategy_store, data_root: Path, *, family: str, regime_tag: str,
    artifact_id: str, count: int, pnl,
) -> None:
    strategy_store.upsert_artifact(
        Artifact(
            artifact_id=artifact_id, type="strategy", name=artifact_id,
            universe=["AAPL"], strategy_family=family, regime_tag=regime_tag,
        )
    )
    log_path = _log_path(data_root)
    for i in range(count):
        value = pnl(i) if callable(pnl) else pnl
        record_exit(
            f"{artifact_id}_trade_{i}", "AAPL",
            {"realized_pnl": value, "artifact_id": artifact_id},
            log_path=log_path,
        )


class TestRegimeStrategyCoverageRun:
    def test_no_data_returns_no_findings(self, strategy_store, data_root):
        assert regime_strategy_coverage.run({"vinu_live": data_root / "vinu_live"}) == []

    def test_below_window_minimum_is_skipped(self, strategy_store, data_root):
        _seed_trades(
            strategy_store, data_root, family="momentum", regime_tag="trend",
            artifact_id="art_1", count=6, pnl=10.0,
        )
        assert regime_strategy_coverage.run({"vinu_live": data_root / "vinu_live"}) == []

    def test_artifact_without_strategy_family_excluded(self, strategy_store, data_root):
        # A pre-existing artifact (created before this field existed) --
        # strategy_family left at its "" default -- must not silently
        # count as its own family.
        strategy_store.upsert_artifact(
            Artifact(artifact_id="legacy", type="strategy", name="legacy", universe=["AAPL"])
        )
        log_path = _log_path(data_root)
        for i in range(15):
            record_exit(f"legacy_trade_{i}", "AAPL", {"realized_pnl": 10.0, "artifact_id": "legacy"}, log_path=log_path)

        assert regime_strategy_coverage.run({"vinu_live": data_root / "vinu_live"}) == []

    def test_drifting_family_is_flagged(self, strategy_store, data_root):
        strategy_store.upsert_artifact(
            Artifact(
                artifact_id="art_1", type="strategy", name="art_1",
                universe=["AAPL"], strategy_family="momentum", regime_tag="trend",
            )
        )
        log_path = _log_path(data_root)
        # 10 reference trades, winning with some real variance.
        reference_pnls = [18.0, 22.0, 19.0, 21.0, 18.0, 22.0, 19.0, 21.0, 18.0, 22.0]
        for i, pnl in enumerate(reference_pnls):
            record_exit(f"art_1_ref_{i}", "AAPL", {"realized_pnl": pnl, "artifact_id": "art_1"}, log_path=log_path)
        # 5 recent trades, losing with some real variance -- a real drift.
        current_pnls = [-18.0, -22.0, -19.0, -21.0, -18.0]
        for i, pnl in enumerate(current_pnls):
            record_exit(f"art_1_cur_{i}", "AAPL", {"realized_pnl": pnl, "artifact_id": "art_1"}, log_path=log_path)

        findings = regime_strategy_coverage.run({"vinu_live": data_root / "vinu_live"})
        assert len(findings) == 1
        finding = findings[0]
        assert finding.scope_type == "strategy_family"
        assert finding.scope_key == "momentum"
        assert finding.metric_name == "family_outcome_trend"
        assert finding.primary_metric < 0
        assert finding.psi > 0.25
        assert finding.evidence_count == 15
        assert finding.signal_json["regime_breakdown"]["trend"]["n"] == 5
        assert finding.signal_json["regime_breakdown"]["trend"]["reward_to_variability"] < 0

    def test_multiple_families_evaluated_independently(self, strategy_store, data_root):
        strategy_store.upsert_artifact(
            Artifact(artifact_id="mom_1", type="strategy", name="mom_1", universe=["AAPL"], strategy_family="momentum")
        )
        strategy_store.upsert_artifact(
            Artifact(artifact_id="mr_1", type="strategy", name="mr_1", universe=["MSFT"], strategy_family="mean_reversion")
        )
        log_path = _log_path(data_root)
        for i in range(15):
            record_exit(f"mom_trade_{i}", "AAPL", {"realized_pnl": 10.0, "artifact_id": "mom_1"}, log_path=log_path)
        # mean_reversion stays below the window minimum.
        for i in range(6):
            record_exit(f"mr_trade_{i}", "MSFT", {"realized_pnl": 5.0, "artifact_id": "mr_1"}, log_path=log_path)

        findings = regime_strategy_coverage.run({"vinu_live": data_root / "vinu_live"})
        assert {f.scope_key for f in findings} == {"momentum"}

    def test_regime_breakdown_splits_by_regime_tag(self, strategy_store, data_root):
        strategy_store.upsert_artifact(
            Artifact(
                artifact_id="trend_art", type="strategy", name="trend_art",
                universe=["AAPL"], strategy_family="momentum", regime_tag="trend",
            )
        )
        strategy_store.upsert_artifact(
            Artifact(
                artifact_id="range_art", type="strategy", name="range_art",
                universe=["AAPL"], strategy_family="momentum", regime_tag="range",
            )
        )
        log_path = _log_path(data_root)
        for i in range(10):
            record_exit(f"trend_ref_{i}", "AAPL", {"realized_pnl": 10.0, "artifact_id": "trend_art"}, log_path=log_path)
        # Current window (last 5, chronologically): mixed regimes.
        for i in range(3):
            record_exit(f"trend_cur_{i}", "AAPL", {"realized_pnl": 10.0, "artifact_id": "trend_art"}, log_path=log_path)
        for i in range(2):
            record_exit(f"range_cur_{i}", "AAPL", {"realized_pnl": -5.0, "artifact_id": "range_art"}, log_path=log_path)

        findings = regime_strategy_coverage.run({"vinu_live": data_root / "vinu_live"})
        assert len(findings) == 1
        breakdown = findings[0].signal_json["regime_breakdown"]
        assert set(breakdown.keys()) == {"trend", "range"}
        assert breakdown["trend"]["n"] == 3
        assert breakdown["range"]["n"] == 2
