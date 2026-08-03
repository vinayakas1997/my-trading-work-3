"""Tests for GroundTruthInjector, focused on the two real bugs found while
building Piece 2 (debrief-on-close): _fetch_open_theses hit the wrong URL
(`/hypotheses` instead of the actual mounted `/research/hypotheses`) and
expected a bare list back when the route actually returns
`{"count": N, "hypotheses": [...]}` — so the "Active Trade Theses" block
had never populated in a real run."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from vinu_agent.audit.ground_truth import GroundTruthInjector


def _injector(services_config: dict | None = None) -> GroundTruthInjector:
    return GroundTruthInjector(registry=MagicMock(), services_config=services_config or {})


class TestFetchOpenTheses:
    def test_hits_the_actual_mounted_research_prefix(self) -> None:
        injector = _injector({"vinu_research": "http://research-api:8087"})
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"count": 0, "hypotheses": []}
        with patch("httpx.get", return_value=mock_resp) as mock_get:
            injector._fetch_open_theses(["AAPL"])
        args, _ = mock_get.call_args
        assert args[0] == "http://research-api:8087/research/hypotheses"

    def test_unwraps_the_hypotheses_list_from_dict_response(self) -> None:
        injector = _injector({"vinu_research": "http://research-api:8087"})
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "count": 1,
            "hypotheses": [
                {"hypothesis_id": "h1", "status": "testing", "universe": ["AAPL"], "thesis": "t"},
            ],
        }
        with patch("httpx.get", return_value=mock_resp):
            result = injector._fetch_open_theses(["AAPL"])
        assert "AAPL" in result
        assert result["AAPL"][0]["hypothesis_id"] == "h1"

    def test_no_service_url_returns_empty(self) -> None:
        injector = _injector({})
        assert injector._fetch_open_theses(["AAPL"]) == {}

    def test_non_200_returns_empty(self) -> None:
        injector = _injector({"vinu_research": "http://research-api:8087"})
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        with patch("httpx.get", return_value=mock_resp):
            assert injector._fetch_open_theses(["AAPL"]) == {}
