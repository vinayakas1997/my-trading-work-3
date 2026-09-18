"""Tests for analyses P + G (ingest health / provider fallback vs. forecast
quality), merged into ingest_health.py's single per-ticker Finding."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from vinu_research.models import Artifact, CalibrationEntry
from vinu_stock.catalog import store as catalog_store_module

from vinu_reflection.reflection import ingest_health


class _FakeTime:
    """Swaps in for the `time` module inside `vinu_stock.catalog.store`
    so `log_ingest`/`record_fallback` (which both call `time.time()`
    internally with no caller-supplied timestamp) can be backdated to a
    specific calendar day -- needed to exercise ingest_health.py's
    day-bucket join against calibration entries dated on specific days."""

    def __init__(self, epoch: float) -> None:
        self._epoch = epoch

    def time(self) -> float:
        return self._epoch


def _epoch_for(date_str: str) -> float:
    return datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc).timestamp()


def _log_ingest_on(monkeypatch, catalog, symbol: str, date_str: str, *, ok: bool) -> None:
    monkeypatch.setattr(catalog_store_module, "time", _FakeTime(_epoch_for(date_str)))
    catalog.log_ingest(symbol, bars_added=1, from_ts=None, to_ts=None, ok=ok, error=None if ok else "boom")


def _record_fallback_on(monkeypatch, catalog, symbol: str, date_str: str) -> None:
    monkeypatch.setattr(catalog_store_module, "time", _FakeTime(_epoch_for(date_str)))
    catalog.record_fallback(symbol, role="bars", winning_provider="polygon", skipped_errors=["alpaca: down"])


@pytest.fixture
def strategy_store(tmp_path, monkeypatch):
    research_root = tmp_path / "research"
    research_root.mkdir()
    monkeypatch.setenv("VINU_RESEARCH_DATA_ROOT", str(research_root))
    return ingest_health.get_strategy_store()


@pytest.fixture
def stock_root(tmp_path) -> Path:
    root = tmp_path / "stock"
    root.mkdir()
    return root


@pytest.fixture
def catalog(stock_root):
    return ingest_health._open_catalog(stock_root / "vinu_stock_price.db")


def _seed_artifacts(strategy_store, *, symbol: str, prefix: str, day: str, count: int, brier: float) -> None:
    created_at = f"{day}T12:00:00+00:00"
    for i in range(count):
        artifact_id = f"{prefix}_{i}"
        strategy_store.upsert_artifact(
            Artifact(
                artifact_id=artifact_id, type="trade_plan", name=artifact_id,
                universe=[symbol], created_at=created_at,
            )
        )
        strategy_store.append_calibration_entry(
            CalibrationEntry(
                artifact_id=artifact_id, forecast_direction="long",
                actual_return_pct=0.01, brier_score=brier,
            )
        )


class TestIngestHealthRun:
    def test_no_stock_root_returns_no_findings(self, strategy_store):
        assert ingest_health.run({}) == []

    def test_missing_db_file_returns_no_findings(self, strategy_store, stock_root):
        assert ingest_health.run({"vinu_stock": str(stock_root)}) == []

    def test_below_min_group_is_skipped(self, strategy_store, catalog, monkeypatch, stock_root):
        catalog.upsert_symbol("AAPL")
        _log_ingest_on(monkeypatch, catalog, "AAPL", "2026-01-05", ok=False)
        _seed_artifacts(strategy_store, symbol="AAPL", prefix="clean", day="2026-01-01", count=2, brier=0.1)
        _seed_artifacts(strategy_store, symbol="AAPL", prefix="bad", day="2026-01-05", count=2, brier=0.6)

        assert ingest_health.run({"vinu_stock": str(stock_root)}) == []

    def test_gap_degraded_symbol_is_flagged(self, strategy_store, catalog, monkeypatch, stock_root):
        catalog.upsert_symbol("AAPL", gap_count=7)
        _log_ingest_on(monkeypatch, catalog, "AAPL", "2026-01-05", ok=False)
        _seed_artifacts(strategy_store, symbol="AAPL", prefix="clean", day="2026-01-01", count=5, brier=0.1)
        # Lands the day after the bad ingest run -- still tainted (1-day lag).
        _seed_artifacts(strategy_store, symbol="AAPL", prefix="bad", day="2026-01-06", count=5, brier=0.6)

        findings = ingest_health.run({"vinu_stock": str(stock_root)})
        assert len(findings) == 1
        finding = findings[0]
        assert finding.scope_type == "ticker"
        assert finding.scope_key == "AAPL"
        assert finding.metric_name == "ingest_brier_delta"
        assert finding.primary_metric == pytest.approx(0.5, abs=1e-6)
        assert finding.psi > 0.25
        assert finding.domain_floor_breached is True
        assert finding.signal_json["gap_count"] == 7
        assert finding.signal_json["brier_delta_vs_clean_periods"] == pytest.approx(0.5, abs=1e-6)
        assert "fallback_brier_delta" not in finding.signal_json

    def test_fallback_degraded_symbol_is_flagged(self, strategy_store, catalog, monkeypatch, stock_root):
        catalog.upsert_symbol("MSFT")
        # ok=True so P's own bad-day set stays empty -- isolates this test to G.
        _log_ingest_on(monkeypatch, catalog, "MSFT", "2026-01-01", ok=True)
        _record_fallback_on(monkeypatch, catalog, "MSFT", "2026-01-10")
        _seed_artifacts(strategy_store, symbol="MSFT", prefix="primary", day="2026-01-01", count=5, brier=0.1)
        _seed_artifacts(strategy_store, symbol="MSFT", prefix="fallback", day="2026-01-10", count=5, brier=0.6)

        findings = ingest_health.run({"vinu_stock": str(stock_root)})
        assert len(findings) == 1
        finding = findings[0]
        assert finding.scope_key == "MSFT"
        assert finding.primary_metric == pytest.approx(0.5, abs=1e-6)
        assert finding.psi > 0.25
        assert finding.signal_json["fallback_brier_delta"] == pytest.approx(0.5, abs=1e-6)
        assert finding.signal_json["fallback_frequency"] == pytest.approx(1.0, abs=1e-6)
        assert "brier_delta_vs_clean_periods" not in finding.signal_json

    def test_stable_symbol_has_low_psi(self, strategy_store, catalog, monkeypatch, stock_root):
        catalog.upsert_symbol("GOOG")
        _log_ingest_on(monkeypatch, catalog, "GOOG", "2026-01-05", ok=False)
        _seed_artifacts(strategy_store, symbol="GOOG", prefix="clean", day="2026-01-01", count=5, brier=0.2)
        _seed_artifacts(strategy_store, symbol="GOOG", prefix="bad", day="2026-01-05", count=5, brier=0.2)

        findings = ingest_health.run({"vinu_stock": str(stock_root)})
        assert len(findings) == 1
        assert findings[0].psi < 0.1
        assert findings[0].domain_floor_breached is False

    def test_multiple_symbols_evaluated_independently(self, strategy_store, catalog, monkeypatch, stock_root):
        catalog.upsert_symbol("AAPL", gap_count=3)
        catalog.upsert_symbol("MSFT", gap_count=0)
        _log_ingest_on(monkeypatch, catalog, "AAPL", "2026-01-05", ok=False)
        _seed_artifacts(strategy_store, symbol="AAPL", prefix="a_clean", day="2026-01-01", count=5, brier=0.1)
        _seed_artifacts(strategy_store, symbol="AAPL", prefix="a_bad", day="2026-01-05", count=5, brier=0.6)
        # MSFT has ingest activity but no bad days and too few calibration
        # entries either side -- shouldn't produce a finding.
        _log_ingest_on(monkeypatch, catalog, "MSFT", "2026-01-01", ok=True)
        _seed_artifacts(strategy_store, symbol="MSFT", prefix="m", day="2026-01-01", count=2, brier=0.1)

        findings = ingest_health.run({"vinu_stock": str(stock_root)})
        assert {f.scope_key for f in findings} == {"AAPL"}
