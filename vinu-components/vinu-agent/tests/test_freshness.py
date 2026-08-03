"""Tests for FreshnessChecker — the reader-side half of the Freshness
Contract (the recompute-trigger half, `regime_recompute_scan()`, lives in
vinu-research and is tested there). This checks that a value's age is
actually evaluated against the threshold and labeled STALE, not just that
the recompute job exists somewhere."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from vinu_agent.audit.freshness import FreshnessChecker


def _angle_response(analysis_at: str, extra_rows: int = 0) -> dict:
    rows = [{"symbol": "JNJ", "angle": "regime_analysis", "analysis_at": analysis_at, "metric": "regime_stats"}]
    for _ in range(extra_rows):
        rows.append({"symbol": "JNJ", "angle": "regime_analysis", "analysis_at": analysis_at, "metric": "transition"})
    return {"symbol": "JNJ", "angle": "regime_analysis", "row_count": len(rows), "data": rows}


def _checker(**kwargs) -> FreshnessChecker:
    return FreshnessChecker(services_config={"vinu_initial_analysis": "http://initial-analysis:8083"}, **kwargs)


class TestFreshnessChecker:
    def test_fresh_data_produces_no_finding(self) -> None:
        recent = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        resp = MagicMock(status_code=200)
        resp.json.return_value = _angle_response(recent)
        with patch("httpx.get", return_value=resp):
            findings = _checker().check_symbols(["JNJ"])
        assert findings == []

    def test_stale_data_is_flagged(self) -> None:
        old = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
        resp = MagicMock(status_code=200)
        resp.json.return_value = _angle_response(old)
        with patch("httpx.get", return_value=resp):
            findings = _checker().check_symbols(["JNJ"])
        assert len(findings) == 1
        assert findings[0]["symbol"] == "JNJ"
        assert findings[0]["age_days"] >= 4.9

    def test_uses_latest_analysis_at_across_multiple_rows(self) -> None:
        old = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
        recent = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        resp = MagicMock(status_code=200)
        payload = _angle_response(old)
        payload["data"].append({"symbol": "JNJ", "angle": "regime_analysis", "analysis_at": recent, "metric": "regime_stats"})
        resp.json.return_value = payload
        with patch("httpx.get", return_value=resp):
            findings = _checker().check_symbols(["JNJ"])
        assert findings == []  # latest row is recent, so not stale

    def test_no_rows_produces_no_finding(self) -> None:
        resp = MagicMock(status_code=200)
        resp.json.return_value = {"symbol": "JNJ", "angle": "regime_analysis", "row_count": 0, "data": []}
        with patch("httpx.get", return_value=resp):
            findings = _checker().check_symbols(["JNJ"])
        assert findings == []

    def test_no_service_url_returns_empty(self) -> None:
        checker = FreshnessChecker(services_config={})
        assert checker.check_symbols(["JNJ"]) == []

    def test_non_200_response_skips_symbol(self) -> None:
        resp = MagicMock(status_code=500)
        with patch("httpx.get", return_value=resp):
            findings = _checker().check_symbols(["JNJ"])
        assert findings == []

    def test_fetch_exception_does_not_raise(self) -> None:
        with patch("httpx.get", side_effect=Exception("network down")):
            findings = _checker().check_symbols(["JNJ"])
        assert findings == []

    def test_custom_threshold_is_respected(self) -> None:
        two_days_old = (datetime.now(timezone.utc) - timedelta(days=2, hours=1)).isoformat()
        resp = MagicMock(status_code=200)
        resp.json.return_value = _angle_response(two_days_old)
        with patch("httpx.get", return_value=resp):
            assert _checker(stale_after_days=1.0).check_symbols(["JNJ"]) != []
            assert _checker(stale_after_days=10.0).check_symbols(["JNJ"]) == []
