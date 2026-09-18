"""Tests for analysis N (Regime & Risk Coverage), reframed around the
nearest quarterly shock-reading snapshot before a real halt. See
missing-pieces-of-system/maturity-agentic-system/thinking-1/
02-decided-pattern/25-A-Y-details/02-regime-risk-coverage.md.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest

from vinu_agent.broker.audit_ledger import HashChainedLedger
from vinu_infra.reflection import ReflectionStore, write_findings

from vinu_reflection.reflection import shock_reading_before_halt as n


@pytest.fixture
def agent_root(tmp_path) -> Path:
    return tmp_path / "agent"


@pytest.fixture
def analysis_root(tmp_path) -> Path:
    return tmp_path / "analysis-root"


def _seed_halt(agent_root: Path, *, ts: datetime, scope: str) -> None:
    ledger = HashChainedLedger(agent_root / "safety_ledger.jsonl")
    ledger._path.parent.mkdir(parents=True, exist_ok=True)
    # Bypass append()'s real datetime.now() timestamp so tests can place
    # the halt at an exact, controlled point relative to the snapshots.
    import json

    entry = {
        "seq": 0, "ts": ts.isoformat(), "event_type": "halt",
        "payload": {"scope": scope}, "prev_hash": "0" * 64, "hash": "x",
    }
    with (agent_root / "safety_ledger.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def _seed_snapshot(
    analysis_root: Path, symbol: str, angle_name: str, field: str, value: float,
    *, stored_at: datetime, run_id: str,
) -> None:
    base = analysis_root / "analysis" / symbol / angle_name / "1D" / "tier2"
    base.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame([{field: value}])
    df["stored_at"] = pd.Timestamp(stored_at).tz_localize(None)
    df.to_parquet(base / f"{run_id}.parquet", index=False)


class TestShockReadingBeforeHaltRun:
    def test_no_halts_returns_no_findings(self, agent_root, analysis_root):
        agent_root.mkdir(parents=True, exist_ok=True)
        findings = n.run({"vinu_agent": agent_root, "vinu_initial_analysis": analysis_root})
        assert findings == []

    def test_below_evidence_minimum_is_skipped(self, agent_root, analysis_root):
        _seed_halt(agent_root, ts=datetime(2026, 6, 1, tzinfo=timezone.utc), scope="AAPL")
        _seed_snapshot(
            analysis_root, "AAPL", "shock_personality", "n_shocks", 5.0,
            stored_at=datetime(2026, 5, 1, tzinfo=timezone.utc), run_id="q1",
        )
        findings = n.run({"vinu_agent": agent_root, "vinu_initial_analysis": analysis_root})
        assert findings == []

    def test_global_halts_are_excluded(self, agent_root, analysis_root):
        _seed_halt(agent_root, ts=datetime(2026, 6, 1, tzinfo=timezone.utc), scope="global")
        for i in range(10):
            _seed_snapshot(
                analysis_root, "AAPL", "shock_personality", "n_shocks", 1.0,
                stored_at=datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(days=30 * i),
                run_id=f"q{i}",
            )
        findings = n.run({"vinu_agent": agent_root, "vinu_initial_analysis": analysis_root})
        assert findings == []

    def test_finds_elevated_shock_reading_before_halt(self, agent_root, analysis_root):
        base_ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
        # AAPL: 3 separate halts, each preceded by an elevated reading,
        # each also preceded by a normal (low) reading further back --
        # 3 halts is exactly MIN_HALT_EVIDENCE.
        for cycle in range(3):
            _seed_snapshot(
                analysis_root, "AAPL", "shock_personality", "n_shocks", 1.0,
                stored_at=base_ts + timedelta(days=180 * cycle), run_id=f"aapl-normal-{cycle}",
            )
            _seed_snapshot(
                analysis_root, "AAPL", "shock_personality", "n_shocks", 20.0,
                stored_at=base_ts + timedelta(days=180 * cycle + 89), run_id=f"aapl-elevated-{cycle}",
            )
            _seed_halt(agent_root, ts=base_ts + timedelta(days=180 * cycle + 90), scope="AAPL")
        # MSFT and other symbols provide extra "normal" baseline evidence,
        # never halted.
        for i in range(5):
            _seed_snapshot(
                analysis_root, "MSFT", "shock_personality", "n_shocks", 1.0,
                stored_at=base_ts + timedelta(days=90 * i), run_id=f"msft-{i}",
            )

        findings = n.run({"vinu_agent": agent_root, "vinu_initial_analysis": analysis_root})
        by_scope = {f.scope_key: f for f in findings}
        assert "kill_switch:shock_personality" in by_scope
        finding = by_scope["kill_switch:shock_personality"]
        assert finding.analyst_name == "shock_reading_before_halt"
        assert finding.scope_type == "system"
        assert finding.signal_json["at_halt_mean"] == pytest.approx(20.0)
        assert finding.signal_json["n_halts_with_reading"] == 3
        assert finding.primary_metric < 0  # at-halt reading ran higher than normal

    def test_halt_with_no_snapshot_before_it_contributes_no_reading(self, agent_root, analysis_root):
        # Halt happens before any snapshot exists for that symbol.
        _seed_halt(agent_root, ts=datetime(2026, 1, 1, tzinfo=timezone.utc), scope="AAPL")
        for i in range(10):
            _seed_snapshot(
                analysis_root, "AAPL", "shock_personality", "n_shocks", 1.0,
                stored_at=datetime(2026, 6, 1, tzinfo=timezone.utc) + timedelta(days=30 * i),
                run_id=f"q{i}",
            )
        findings = n.run({"vinu_agent": agent_root, "vinu_initial_analysis": analysis_root})
        assert findings == []


class TestShockReadingBeforeHaltEndToEnd:
    def test_run_write_findings_round_trip(self, agent_root, analysis_root):
        reflection_store = ReflectionStore(analysis_root / "reflection.db")
        n.seed_reference_config(reflection_store)

        base_ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
        for cycle in range(3):
            _seed_snapshot(
                analysis_root, "AAPL", "shock_personality", "n_shocks", 1.0,
                stored_at=base_ts + timedelta(days=180 * cycle), run_id=f"aapl-normal-{cycle}",
            )
            _seed_snapshot(
                analysis_root, "AAPL", "shock_personality", "n_shocks", 20.0,
                stored_at=base_ts + timedelta(days=180 * cycle + 89), run_id=f"aapl-elevated-{cycle}",
            )
            _seed_halt(agent_root, ts=base_ts + timedelta(days=180 * cycle + 90), scope="AAPL")
        for i in range(5):
            _seed_snapshot(
                analysis_root, "MSFT", "shock_personality", "n_shocks", 1.0,
                stored_at=base_ts + timedelta(days=90 * i), run_id=f"msft-{i}",
            )

        findings = n.run({"vinu_agent": agent_root, "vinu_initial_analysis": analysis_root})
        written = write_findings(reflection_store, findings)
        assert len(written) >= 1

        belief = reflection_store.get_belief(
            "shock_reading_before_halt", "system", "kill_switch:shock_personality",
        )
        assert belief is not None
