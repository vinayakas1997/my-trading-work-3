from __future__ import annotations

import math

from vinu_research.angle_context import (
    build_angle_context,
    compact_news_causality,
    compact_session_structure,
    compact_trend_lifecycle,
)


def _tl_row(run_id, stored_at, row_type, tf="1D", **extra):
    row = {
        "run_id": run_id, "stored_at": stored_at,
        "type": row_type, "time_format": tf,
    }
    row.update(extra)
    return row


class TestTrendLifecycle:
    def test_latest_run_wins(self):
        rows = [
            _tl_row("aaa", "2026-01-01T00:00:00", "lifecycle", stage="uptrend", risk="low"),
            _tl_row("bbb", "2026-02-01T00:00:00", "lifecycle", stage="topping", risk="high"),
        ]
        out = compact_trend_lifecycle(rows, "1D")
        assert out["stage"] == "topping"
        assert out["risk"] == "high"

    def test_time_format_filter(self):
        rows = [
            _tl_row("bbb", "2026-02-01T00:00:00", "lifecycle", tf="1H", stage="downtrend"),
            _tl_row("bbb", "2026-02-01T00:00:00", "lifecycle", tf="1D", stage="uptrend"),
        ]
        out = compact_trend_lifecycle(rows, "1D")
        assert out["stage"] == "uptrend"

    def test_highest_confidence_signal_selected_and_nan_cleaned(self):
        rows = [
            _tl_row("bbb", "2026-02-01T00:00:00", "signal",
                    signal_type="hold", confidence=0.5, suggested_action="Hold.",
                    avg_drawdown_pct=math.nan, exit_threshold_pct=None),
            _tl_row("bbb", "2026-02-01T00:00:00", "signal",
                    signal_type="book_profits", confidence=0.9,
                    suggested_action="Set trailing stop at -4%",
                    avg_drawdown_pct=-0.08, exit_threshold_pct=-4.0),
        ]
        out = compact_trend_lifecycle(rows, "1D")
        assert out["signal"]["signal_type"] == "book_profits"
        assert out["signal"]["exit_threshold_pct"] == -4.0

    def test_empty_returns_none(self):
        assert compact_trend_lifecycle([], "1D") is None


class TestSessionStructure:
    def _rows(self, tf="1H"):
        return [
            _tl_row("bbb", "2026-02-01T00:00:00", "session_stats", tf=tf,
                    session="regular", n_peaks=12, n_mature_peaks=12,
                    meets_floor=True, avg_drawdown_pct=-0.05, recovery_rate=0.8),
            _tl_row("bbb", "2026-02-01T00:00:00", "summary", tf=tf,
                    status="completed", best_session="regular",
                    worst_session="premarket", n_qualifying_sessions=2),
        ]

    def test_exact_time_format(self):
        out = compact_session_structure(self._rows("1H"), "1H")
        assert out["worst_session"] == "premarket"
        assert out["time_format"] == "1H"
        assert out["sessions"][0]["session"] == "regular"

    def test_intraday_fallback_for_daily_research(self):
        # Daily research still surfaces intraday session structure, labeled
        out = compact_session_structure(self._rows("1H"), "1D")
        assert out is not None
        assert out["time_format"] == "1H"

    def test_empty_returns_none(self):
        assert compact_session_structure([], "1H") is None


class TestNewsCausality:
    def test_merges_typed_rows(self):
        rows = [
            {"run_id": "x", "stored_at": "2026-02-01", "type": "granger",
             "granger_causes_prices": True, "best_lag_minutes": 30,
             "p_value": 0.01, "sample_size": 500},
            {"run_id": "x", "stored_at": "2026-02-01", "type": "correlation",
             "news_return_corr": 0.22, "corr_p_value": 0.03,
             "sentiment_return_corr": 0.15, "news_volume_corr": math.nan},
        ]
        out = compact_news_causality(rows)
        assert out["granger_causes_prices"] is True
        assert out["best_lag_minutes"] == 30
        assert out["news_return_corr"] == 0.22
        assert "news_volume_corr" not in out  # NaN dropped

    def test_empty_returns_none(self):
        assert compact_news_causality([]) is None


class TestBuildAngleContext:
    def test_all_empty_gives_empty_dict(self):
        assert build_angle_context([], [], [], interval="1d") == {}

    def test_interval_mapping(self):
        trend = [_tl_row("bbb", "2026-02-01T00:00:00", "lifecycle", tf="1H", stage="basing", risk="low")]
        ctx = build_angle_context(trend, [], [], interval="1h")
        assert ctx["trend_lifecycle"]["stage"] == "basing"
        # daily research must not pick up the 1H lifecycle row
        assert build_angle_context(trend, [], [], interval="1d") == {}
