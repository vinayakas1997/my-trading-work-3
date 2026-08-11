"""Tests for GroundTruthInjector's _fetch_open_theses / _fetch_all_hypotheses.

Reads HypothesisRegistry's real local store in-process first (see
vinu_agent/broker/research_link.py), falling back to HTTP only if that
raises. The HTTP-focused tests below force the fallback the same way
test_debrief.py/test_trade_plan_calibration.py do, by patching
research_link's own getter to raise -- also covers the two real bugs
found while building Piece 2 (debrief-on-close): _fetch_open_theses hit
the wrong URL (`/hypotheses` instead of the actual mounted
`/research/hypotheses`) and expected a bare list back when the route
actually returns `{"count": N, "hypotheses": [...]}`.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from vinu_agent.audit.ground_truth import GroundTruthInjector
from vinu_research.hypothesis_registry import HypothesisRegistry
from vinu_research.models import Hypothesis, HypothesisStatus


def _injector(services_config: dict | None = None) -> GroundTruthInjector:
    return GroundTruthInjector(registry=MagicMock(), services_config=services_config or {})


def _force_in_process_unavailable():
    return patch(
        "vinu_agent.broker.research_link.get_hypothesis_registry",
        side_effect=RuntimeError("not available"),
    )


@pytest.fixture
def hypothesis_registry(tmp_path) -> HypothesisRegistry:
    return HypothesisRegistry(path=tmp_path / "hypotheses.json")


class TestFetchOpenThesesInProcess:
    def test_reads_real_open_hypothesis_for_symbol(self, hypothesis_registry: HypothesisRegistry) -> None:
        h = Hypothesis.create(title="t", thesis="mean reversion works", universe=["AAPL"])
        h.status = HypothesisStatus.testing
        hypothesis_registry.create(h)

        with patch("vinu_agent.broker.research_link.get_hypothesis_registry", return_value=hypothesis_registry):
            result = _injector()._fetch_open_theses(["AAPL"])

        assert "AAPL" in result
        assert result["AAPL"][0]["hypothesis_id"] == h.hypothesis_id

    def test_excludes_non_open_statuses(self, hypothesis_registry: HypothesisRegistry) -> None:
        h = Hypothesis.create(title="t", thesis="rejected idea", universe=["AAPL"])
        h.status = HypothesisStatus.rejected
        hypothesis_registry.create(h)

        with patch("vinu_agent.broker.research_link.get_hypothesis_registry", return_value=hypothesis_registry):
            result = _injector()._fetch_open_theses(["AAPL"])

        assert result == {}

    def test_falls_back_to_http_when_in_process_raises(self) -> None:
        injector = _injector({"vinu_research": "http://research-api:8087"})
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "count": 1,
            "hypotheses": [
                {"hypothesis_id": "h1", "status": "testing", "universe": ["AAPL"], "thesis": "t"},
            ],
        }
        with _force_in_process_unavailable(), patch("httpx.get", return_value=mock_resp):
            result = injector._fetch_open_theses(["AAPL"])
        assert result["AAPL"][0]["hypothesis_id"] == "h1"


class TestFetchOpenThesesHttpFallback:
    def test_hits_the_actual_mounted_research_prefix(self) -> None:
        injector = _injector({"vinu_research": "http://research-api:8087"})
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"count": 0, "hypotheses": []}
        with _force_in_process_unavailable(), patch("httpx.get", return_value=mock_resp) as mock_get:
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
        with _force_in_process_unavailable(), patch("httpx.get", return_value=mock_resp):
            result = injector._fetch_open_theses(["AAPL"])
        assert "AAPL" in result
        assert result["AAPL"][0]["hypothesis_id"] == "h1"

    def test_no_service_url_returns_empty(self) -> None:
        injector = _injector({})
        with _force_in_process_unavailable():
            assert injector._fetch_open_theses(["AAPL"]) == {}

    def test_non_200_returns_empty(self) -> None:
        injector = _injector({"vinu_research": "http://research-api:8087"})
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        with _force_in_process_unavailable(), patch("httpx.get", return_value=mock_resp):
            assert injector._fetch_open_theses(["AAPL"]) == {}
