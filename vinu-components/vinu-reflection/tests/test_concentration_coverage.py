"""Tests for analysis E, concentration piece (per-sleeve weight
concentration drift)."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from vinu_portfolio.storage.allocation_history import AllocationHistoryStore

from vinu_reflection.reflection import concentration_coverage


@pytest.fixture
def data_root(tmp_path) -> Path:
    return tmp_path


def _seed_days(store: AllocationHistoryStore, *, n: int, sleeve_weight: float, start_offset: int) -> None:
    base = date(2026, 1, 1)
    for i in range(n):
        d = base + timedelta(days=start_offset + i)
        store.record_daily_allocation(
            allocation_date=d.isoformat(),
            sleeves={"momentum": sleeve_weight},
        )


class TestConcentrationCoverageRun:
    def test_no_data_returns_no_findings(self, data_root):
        AllocationHistoryStore(str(data_root / "allocation_history.db"))
        assert concentration_coverage.run({"vinu_portfolio": data_root}) == []

    def test_below_window_minimum_is_skipped(self, data_root):
        store = AllocationHistoryStore(str(data_root / "allocation_history.db"))
        _seed_days(store, n=40, sleeve_weight=0.2, start_offset=0)
        assert concentration_coverage.run({"vinu_portfolio": data_root}) == []

    def test_rising_concentration_is_flagged(self, data_root):
        store = AllocationHistoryStore(str(data_root / "allocation_history.db"))
        _seed_days(store, n=90, sleeve_weight=0.1, start_offset=0)
        _seed_days(store, n=30, sleeve_weight=0.6, start_offset=90)

        findings = concentration_coverage.run({"vinu_portfolio": data_root})
        assert len(findings) == 1
        finding = findings[0]
        assert finding.scope_type == "strategy_family"
        assert finding.scope_key == "momentum"
        assert finding.metric_name == "weight_trend"
        assert finding.primary_metric == pytest.approx(0.5, abs=1e-6)
        assert finding.psi > 0.25
        assert finding.evidence_count == 120

    def test_stable_concentration_has_low_psi(self, data_root):
        store = AllocationHistoryStore(str(data_root / "allocation_history.db"))
        _seed_days(store, n=120, sleeve_weight=0.3, start_offset=0)

        findings = concentration_coverage.run({"vinu_portfolio": data_root})
        assert len(findings) == 1
        assert findings[0].psi < 0.1

    def test_multiple_sleeves_evaluated_independently(self, data_root):
        store = AllocationHistoryStore(str(data_root / "allocation_history.db"))
        base = date(2026, 1, 1)
        for i in range(120):
            d = base + timedelta(days=i)
            weight = 0.1 if i < 90 else 0.6
            store.record_daily_allocation(
                allocation_date=d.isoformat(),
                sleeves={"momentum": weight, "meanrev": 0.2},
            )

        findings = concentration_coverage.run({"vinu_portfolio": data_root})
        by_sleeve = {f.scope_key: f for f in findings}
        assert "momentum" in by_sleeve
        assert "meanrev" in by_sleeve
        assert by_sleeve["momentum"].psi > 0.25
        assert by_sleeve["meanrev"].psi < 0.1
