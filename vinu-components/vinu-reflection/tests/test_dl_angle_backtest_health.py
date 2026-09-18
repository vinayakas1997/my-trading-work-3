"""Tests for analysis Q (Forecast Intelligence), reframed around each DL
angle's own backtest-accuracy history. See missing-pieces-of-system/
maturity-agentic-system/thinking-1/02-decided-pattern/25-A-Y-details/
01-forecast-intelligence.md.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest

from vinu_infra.reflection import ReflectionStore, write_findings

from vinu_reflection.reflection import dl_angle_backtest_health as q


@pytest.fixture
def data_root(tmp_path) -> Path:
    return tmp_path


def _write_backtest_run(
    data_root: Path, symbol: str, angle_name: str, hits: list[int], *,
    stored_at: datetime | None = None,
) -> None:
    base = data_root / "analysis" / symbol / angle_name / "1D" / "tier2"
    base.mkdir(parents=True, exist_ok=True)
    rows = [
        {"bar_ts": i, "hit": h, "weights_ref": f"{symbol}/{angle_name}/1D/2026/202601/{i}.pt"}
        for i, h in enumerate(hits)
    ]
    df = pd.DataFrame(rows)
    df["stored_at"] = pd.Timestamp(stored_at or datetime.now(timezone.utc)).tz_localize(None)
    df.to_parquet(base / "run1.parquet", index=False)


class TestDlAngleBacktestHealthRun:
    def test_no_data_returns_no_findings(self, data_root):
        findings = q.run({"vinu_initial_analysis": data_root})
        assert findings == []

    def test_below_evidence_minimum_is_skipped(self, data_root):
        _write_backtest_run(data_root, "AAPL", "lstm", [1] * 10)
        findings = q.run({"vinu_initial_analysis": data_root})
        assert findings == []

    def test_finds_declining_hit_rate(self, data_root):
        # Reference window: 90 hits (perfect). Current window: 30 misses.
        hits = [1] * 90 + [0] * 30
        _write_backtest_run(data_root, "AAPL", "lstm", hits)

        findings = q.run({"vinu_initial_analysis": data_root})
        by_metric = {f.metric_name: f for f in findings}
        assert "hit_rate_trend" in by_metric
        finding = by_metric["hit_rate_trend"]
        assert finding.analyst_name == "dl_angle_backtest_health"
        assert finding.scope_type == "ticker"
        assert finding.scope_key == "AAPL:lstm"
        assert finding.signal_json["hit_rate"] == pytest.approx(0.0)
        assert finding.signal_json["reference_hit_rate"] == pytest.approx(1.0)
        assert finding.primary_metric == pytest.approx(-1.0)

    def test_non_dl_angle_names_are_never_read(self, data_root):
        # arima has no weights_ref/hit history worth reading (see module
        # docstring) -- not in DL_ANGLES, so it's simply never touched,
        # even if data happens to exist under that name.
        _write_backtest_run(data_root, "AAPL", "arima", [1] * 200)
        findings = q.run({"vinu_initial_analysis": data_root})
        assert findings == []

    def test_finds_stale_backtest_record(self, data_root, monkeypatch):
        monkeypatch.setenv("VINU_TIER2_PERIOD_MONTHS", "3")
        old_stored_at = datetime.now(timezone.utc) - timedelta(days=400)
        _write_backtest_run(data_root, "AAPL", "tft", [1] * 10, stored_at=old_stored_at)

        findings = q.run({"vinu_initial_analysis": data_root})
        by_metric = {f.metric_name: f for f in findings}
        assert "backtest_staleness_days" in by_metric
        finding = by_metric["backtest_staleness_days"]
        assert finding.scope_key == "AAPL:tft:staleness"
        assert finding.primary_metric > 180

    def test_recent_backtest_record_is_not_stale(self, data_root):
        _write_backtest_run(data_root, "AAPL", "tft", [1] * 10)
        findings = q.run({"vinu_initial_analysis": data_root})
        assert not any(f.metric_name == "backtest_staleness_days" for f in findings)


class TestDlAngleBacktestHealthEndToEnd:
    def test_run_write_findings_round_trip(self, data_root):
        reflection_store = ReflectionStore(data_root / "reflection.db")
        q.seed_reference_config(reflection_store)

        hits = [1] * 90 + [0] * 30
        _write_backtest_run(data_root, "AAPL", "lstm", hits)

        findings = q.run({"vinu_initial_analysis": data_root})
        written = write_findings(reflection_store, findings)
        assert len(written) >= 1

        belief = reflection_store.get_belief("dl_angle_backtest_health", "ticker", "AAPL:lstm")
        assert belief is not None
