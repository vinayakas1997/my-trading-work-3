import numpy as np
import pandas as pd
import pytest

from vinu_initial_analysis.angles.trend_session_structure.sessions import (
    dedup_latest_snapshots,
    aggregate_sessions,
    build_summary,
    _MIN_SAMPLE,
)
from vinu_initial_analysis.angles.trend_session_structure import compute as tss_compute


def _peak_row(bar_ts, session, drawdown=-0.05, recovery=10, mature=True, stored_at="2026-01-01T00:00:00", **extra):
    row = {
        "type": "snapshot",
        "inflection_type": "peak",
        "bar_ts": bar_ts,
        "session": session,
        "drawdown_pct": drawdown,
        "recovery_time_bars": recovery,
        "outcome_mature": mature,
        "stored_at": stored_at,
        "runup_bars": 20,
        "volume_zscore_20": 1.0,
        "upper_wick_pct": 0.3,
    }
    row.update(extra)
    return row


def test_dedup_keeps_latest_stored_row():
    # Same peak stored twice: first immature (truncated outcome), then recaptured mature
    df = pd.DataFrame([
        _peak_row(1000, "regular", drawdown=-0.01, mature=False, stored_at="2026-01-01T00:00:00"),
        _peak_row(1000, "regular", drawdown=-0.08, mature=True, stored_at="2026-01-05T00:00:00"),
        _peak_row(2000, "regular", drawdown=-0.03, mature=True, stored_at="2026-01-01T00:00:00"),
    ])
    result = dedup_latest_snapshots(df)
    assert len(result) == 2
    row = result[result["bar_ts"] == 1000].iloc[0]
    assert row["drawdown_pct"] == -0.08
    assert row["outcome_mature"] == True  # noqa: E712


def test_floor_suppression_and_stats():
    # regular: 12 mature peaks (above floor); afterhours: 3 (below floor)
    rows = [_peak_row(1000 + i, "regular", drawdown=-0.04 - i * 0.001, recovery=5 + i) for i in range(12)]
    rows += [_peak_row(50000 + i, "afterhours", drawdown=-0.10) for i in range(3)]
    snaps = pd.DataFrame(rows)
    stats = {r["session"]: r for r in aggregate_sessions(snaps)}

    reg = stats["regular"]
    assert reg["n_peaks"] == 12 and reg["n_mature_peaks"] == 12
    assert reg["meets_floor"] is True
    assert reg["avg_drawdown_pct"] == pytest.approx(-0.0455, abs=1e-4)
    assert reg["recovery_rate"] == 1.0
    assert reg["worst_drawdown_pct"] == pytest.approx(-0.051, abs=1e-4)

    ah = stats["afterhours"]
    assert ah["n_peaks"] == 3
    assert ah["meets_floor"] is False
    # Counts reported, but rates/averages suppressed below the floor
    assert ah["avg_drawdown_pct"] is None
    assert ah["recovery_rate"] is None


def test_zero_drawdown_included_no_truthiness_bug():
    rows = [_peak_row(1000 + i, "regular", drawdown=0.0, recovery=None) for i in range(_MIN_SAMPLE)]
    stats = aggregate_sessions(pd.DataFrame(rows))
    reg = [r for r in stats if r["session"] == "regular"][0]
    # 0.0 drawdowns must be averaged in, not dropped as falsy
    assert reg["avg_drawdown_pct"] == 0.0
    assert reg["recovery_rate"] == 0.0


def test_immature_counted_but_excluded_from_stats():
    rows = [_peak_row(1000 + i, "regular", drawdown=-0.05) for i in range(_MIN_SAMPLE)]
    rows.append(_peak_row(9999, "regular", drawdown=-0.50, mature=False))
    stats = aggregate_sessions(pd.DataFrame(rows))
    reg = [r for r in stats if r["session"] == "regular"][0]
    assert reg["n_peaks"] == _MIN_SAMPLE + 1
    assert reg["n_mature_peaks"] == _MIN_SAMPLE
    # The -0.50 immature outcome must not poison the average
    assert reg["avg_drawdown_pct"] == pytest.approx(-0.05)


def test_match_similarity_attributed_to_correct_session():
    snaps = pd.DataFrame(
        [_peak_row(1000 + i, "regular") for i in range(3)]
        + [_peak_row(50000 + i, "premarket") for i in range(3)]
    )
    matches = pd.DataFrame(
        [{"type": "match", "query_bar_ts": 1000, "similarity": 0.9} for _ in range(5)]
        + [{"type": "match", "query_bar_ts": 50000, "similarity": 0.2} for _ in range(2)]
    )
    stats = {r["session"]: r for r in aggregate_sessions(snaps, matches)}
    assert stats["regular"]["n_matches"] == 5
    assert stats["regular"]["avg_similarity"] == pytest.approx(0.9)
    # premarket has only 2 matches -> below similarity floor, count still reported
    assert stats["premarket"]["n_matches"] == 2
    assert stats["premarket"]["avg_similarity"] is None


def test_summary_ranks_only_qualifying_sessions():
    rows = [_peak_row(1000 + i, "regular", drawdown=-0.03) for i in range(_MIN_SAMPLE)]
    rows += [_peak_row(30000 + i, "premarket", drawdown=-0.09) for i in range(_MIN_SAMPLE)]
    rows += [_peak_row(60000 + i, "afterhours", drawdown=-0.50) for i in range(2)]  # below floor
    stats = aggregate_sessions(pd.DataFrame(rows))
    summary = build_summary(stats)
    assert summary["n_qualifying_sessions"] == 2
    assert summary["best_session"] == "regular"      # shallowest avg drawdown
    assert summary["worst_session"] == "premarket"   # afterhours excluded despite -0.50
    assert summary["total_peaks"] == 2 * _MIN_SAMPLE + 2


def test_compute_no_upstream_data(monkeypatch, tmp_path):
    monkeypatch.setenv("VINU_INITIAL_ANALYSIS_DATA_ROOT", str(tmp_path))
    df = tss_compute.compute("NO_SUCH_SYMBOL", time_format="1H")
    assert df.iloc[0]["status"] == "no_upstream_data"


def test_compute_not_applicable_for_daily():
    df = tss_compute.compute("ANY", time_format="1D")
    assert df.iloc[0]["status"] == "not_applicable"
