"""Tests for ResearchDigestReader — the missing "how does the agent/user
find out what happened" piece after a vinu-research run. Confirms a new
run's plain-English summary_text surfaces once, and only once, not on
every subsequent turn."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vinu_agent.audit.research_digest import ResearchDigestReader


def _runs_response(run_id: int, summary_text: str = "Tried momentum, Sharpe 1.4.", best_sharpe: float = 1.4) -> list[dict]:
    return [{"id": run_id, "symbol": "AAPL", "summary_text": summary_text, "best_sharpe": best_sharpe, "status": "done"}]


@pytest.fixture
def state_path() -> Path:
    tmp = Path(tempfile.mktemp(suffix=".json"))
    yield tmp
    tmp.unlink(missing_ok=True)


def _reader(state_path: Path) -> ResearchDigestReader:
    return ResearchDigestReader(
        services_config={"vinu_research": "http://research-api:8087"}, state_path=state_path,
    )


class TestResearchDigestReader:
    def test_new_run_surfaces_on_first_check(self, state_path: Path):
        resp = MagicMock(status_code=200)
        resp.json.return_value = _runs_response(run_id=7)
        with patch("httpx.get", return_value=resp):
            findings = _reader(state_path).check_symbols(["AAPL"])
        assert len(findings) == 1
        assert findings[0]["run_id"] == 7
        assert findings[0]["summary_text"] == "Tried momentum, Sharpe 1.4."

    def test_same_run_does_not_repeat_on_second_check(self, state_path: Path):
        resp = MagicMock(status_code=200)
        resp.json.return_value = _runs_response(run_id=7)
        reader = _reader(state_path)
        with patch("httpx.get", return_value=resp):
            first = reader.check_symbols(["AAPL"])
            second = reader.check_symbols(["AAPL"])
        assert len(first) == 1
        assert second == []

    def test_new_run_id_surfaces_again(self, state_path: Path):
        reader = _reader(state_path)
        resp1 = MagicMock(status_code=200)
        resp1.json.return_value = _runs_response(run_id=7)
        with patch("httpx.get", return_value=resp1):
            reader.check_symbols(["AAPL"])

        resp2 = MagicMock(status_code=200)
        resp2.json.return_value = _runs_response(run_id=8, summary_text="Pivoted to mean-reversion, Sharpe 0.9.")
        with patch("httpx.get", return_value=resp2):
            findings = reader.check_symbols(["AAPL"])
        assert len(findings) == 1
        assert findings[0]["run_id"] == 8

    def test_empty_summary_text_is_skipped(self, state_path: Path):
        resp = MagicMock(status_code=200)
        resp.json.return_value = _runs_response(run_id=7, summary_text="")
        with patch("httpx.get", return_value=resp):
            findings = _reader(state_path).check_symbols(["AAPL"])
        assert findings == []

    def test_no_runs_produces_no_finding(self, state_path: Path):
        resp = MagicMock(status_code=200)
        resp.json.return_value = []
        with patch("httpx.get", return_value=resp):
            findings = _reader(state_path).check_symbols(["AAPL"])
        assert findings == []

    def test_no_service_url_returns_empty(self, state_path: Path):
        reader = ResearchDigestReader(services_config={}, state_path=state_path)
        assert reader.check_symbols(["AAPL"]) == []

    def test_non_200_response_skips_symbol(self, state_path: Path):
        resp = MagicMock(status_code=500)
        with patch("httpx.get", return_value=resp):
            findings = _reader(state_path).check_symbols(["AAPL"])
        assert findings == []

    def test_fetch_exception_does_not_raise(self, state_path: Path):
        with patch("httpx.get", side_effect=Exception("network down")):
            findings = _reader(state_path).check_symbols(["AAPL"])
        assert findings == []

    def test_no_symbols_returns_empty_without_calling_http(self, state_path: Path):
        with patch("httpx.get") as mock_get:
            findings = _reader(state_path).check_symbols([])
        assert findings == []
        mock_get.assert_not_called()
