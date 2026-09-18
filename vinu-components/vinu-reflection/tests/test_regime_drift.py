"""Tests for analysis J (External-Signal Cross-Check) -- is the whole-
market regime drifting. See missing-pieces-of-system/maturity-agentic-
system/thinking-1/02-decided-pattern/25-A-Y-details/
06-external-signal-cross-check.md.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from vinu_infra.reflection import ReflectionStore, write_findings
from vinu_research.storage.market_regime_history import MarketRegimeHistoryStore

from vinu_reflection.reflection import regime_drift


@pytest.fixture
def data_root(tmp_path, monkeypatch) -> Path:
    # regime_drift.run() reads MarketRegimeHistoryStore via
    # get_market_regime_history_store() (VINU_RESEARCH_DATA_ROOT), same as
    # B/V/O -- data_root_paths has no "vinu_research" key in the real wiring.
    monkeypatch.setenv("VINU_RESEARCH_DATA_ROOT", str(tmp_path))
    return tmp_path


def _seed_days(store: MarketRegimeHistoryStore, *, start_day: int, count: int, positive_ratio: float) -> None:
    for i in range(count):
        day = start_day + i
        store.record(
            f"2026-01-{day:02d}",
            {
                "n_matches": 5, "n_positive": round(5 * positive_ratio), "n_negative": 5,
                "positive_ratio": positive_ratio, "avg_return": 0.01, "median_return": 0.01,
                "max_drawdown": -0.02,
            },
        )


class TestRegimeDriftRun:
    def test_no_data_returns_no_findings(self, data_root):
        MarketRegimeHistoryStore(data_root / "market_regime_history.db")
        findings = regime_drift.run({})
        assert findings == []

    def test_below_evidence_minimum_is_skipped(self, data_root):
        store = MarketRegimeHistoryStore(data_root / "market_regime_history.db")
        _seed_days(store, start_day=1, count=10, positive_ratio=0.7)

        findings = regime_drift.run({})
        assert findings == []

    def test_finds_falling_positive_ratio(self, data_root):
        store = MarketRegimeHistoryStore(data_root / "market_regime_history.db")
        # Reference window: 30 days of a favorable regime.
        _seed_days(store, start_day=1, count=30, positive_ratio=0.9)
        # Current window: 10 days of a much less favorable regime.
        _seed_days(store, start_day=31, count=10, positive_ratio=0.1)

        findings = regime_drift.run({})
        assert len(findings) == 1
        finding = findings[0]
        assert finding.analyst_name == "regime_drift"
        assert finding.scope_type == "system"
        assert finding.scope_key == "market_regime"
        assert finding.metric_name == "positive_ratio_trend"
        assert finding.signal_json["positive_ratio"] == pytest.approx(0.1)
        assert finding.signal_json["reference_positive_ratio"] == pytest.approx(0.9)
        assert finding.primary_metric == pytest.approx(-0.8)

    def test_stable_positive_ratio_finds_low_psi(self, data_root):
        store = MarketRegimeHistoryStore(data_root / "market_regime_history.db")
        _seed_days(store, start_day=1, count=30, positive_ratio=0.6)
        _seed_days(store, start_day=31, count=10, positive_ratio=0.6)

        findings = regime_drift.run({})
        assert len(findings) == 1
        assert findings[0].psi == pytest.approx(0.0, abs=1e-6)


class TestRegimeDriftEndToEnd:
    def test_run_write_findings_round_trip(self, data_root):
        store = MarketRegimeHistoryStore(data_root / "market_regime_history.db")
        reflection_store = ReflectionStore(data_root / "reflection.db")
        regime_drift.seed_reference_config(reflection_store)

        _seed_days(store, start_day=1, count=30, positive_ratio=0.9)
        _seed_days(store, start_day=31, count=10, positive_ratio=0.1)

        findings = regime_drift.run({})
        written = write_findings(reflection_store, findings)
        assert len(written) >= 1

        belief = reflection_store.get_belief("regime_drift", "system", "market_regime")
        assert belief is not None
