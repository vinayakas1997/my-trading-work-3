import json
from unittest.mock import MagicMock, patch

import pytest

from vinu_agent.tools.query_hypotheses_tool import QueryHypothesesTool
from vinu_research.hypothesis_registry import HypothesisRegistry
from vinu_research.models import Hypothesis, HypothesisStatus


def _tool(services_config: dict | None = None) -> QueryHypothesesTool:
    tool = QueryHypothesesTool()
    tool._services_config = services_config or {}
    return tool


def _force_in_process_unavailable():
    return patch(
        "vinu_agent.broker.research_link.get_hypothesis_registry",
        side_effect=RuntimeError("not available"),
    )


@pytest.fixture
def hypothesis_registry(tmp_path) -> HypothesisRegistry:
    return HypothesisRegistry(path=tmp_path / "hypotheses.json")


class TestQueryHypothesesToolInProcess:
    def test_lists_real_hypotheses_with_no_filters(self, hypothesis_registry) -> None:
        h = Hypothesis.create(title="t", thesis="th", universe=["AAPL"])
        hypothesis_registry.create(h)
        tool = _tool()
        with patch("vinu_agent.broker.research_link.get_hypothesis_registry", return_value=hypothesis_registry):
            result = json.loads(tool.execute())
        assert result["count"] == 1
        assert result["hypotheses"][0]["hypothesis_id"] == h.hypothesis_id

    def test_filters_by_symbol_and_status(self, hypothesis_registry) -> None:
        matching = Hypothesis.create(title="t1", thesis="th1", universe=["AAPL"])
        matching.status = HypothesisStatus.validated
        hypothesis_registry.create(matching)
        other_symbol = Hypothesis.create(title="t2", thesis="th2", universe=["MSFT"])
        other_symbol.status = HypothesisStatus.validated
        hypothesis_registry.create(other_symbol)
        wrong_status = Hypothesis.create(title="t3", thesis="th3", universe=["AAPL"])
        hypothesis_registry.create(wrong_status)

        tool = _tool()
        with patch("vinu_agent.broker.research_link.get_hypothesis_registry", return_value=hypothesis_registry):
            result = json.loads(tool.execute(symbol="AAPL", status="validated"))

        assert result["count"] == 1
        assert result["hypotheses"][0]["hypothesis_id"] == matching.hypothesis_id

    def test_falls_back_to_http_when_in_process_raises(self) -> None:
        tool = _tool({"vinu_research": "http://research-api:8087"})
        mock_resp = MagicMock()
        mock_resp.text = '{"count": 0, "hypotheses": []}'
        with _force_in_process_unavailable(), patch("httpx.get", return_value=mock_resp) as mock_get:
            result = tool.execute()
        mock_get.assert_called_once()
        assert result == '{"count": 0, "hypotheses": []}'


class TestQueryHypothesesToolHttpFallback:
    def test_uses_configured_service_url_and_prefix(self) -> None:
        tool = _tool({"vinu_research": "http://research-api:8087"})
        mock_resp = MagicMock()
        mock_resp.text = '{"count": 0, "hypotheses": []}'
        with _force_in_process_unavailable(), patch("httpx.get", return_value=mock_resp) as mock_get:
            result = tool.execute()
        args, kwargs = mock_get.call_args
        assert args[0] == "http://research-api:8087/research/hypotheses"
        assert kwargs["params"] == {}
        assert result == '{"count": 0, "hypotheses": []}'

    def test_falls_back_to_default_url(self) -> None:
        tool = _tool()
        mock_resp = MagicMock()
        mock_resp.text = "{}"
        with _force_in_process_unavailable(), patch("httpx.get", return_value=mock_resp) as mock_get:
            tool.execute()
        args, _ = mock_get.call_args
        assert args[0] == "http://localhost:8087/research/hypotheses"

    def test_passes_symbol_and_status_filters(self) -> None:
        tool = _tool()
        mock_resp = MagicMock()
        mock_resp.text = "{}"
        with _force_in_process_unavailable(), patch("httpx.get", return_value=mock_resp) as mock_get:
            tool.execute(symbol="AAPL", status="validated")
        _, kwargs = mock_get.call_args
        assert kwargs["params"] == {"symbol": "AAPL", "status": "validated"}

    def test_raises_on_http_error(self) -> None:
        tool = _tool()
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = RuntimeError("boom")
        with _force_in_process_unavailable(), patch("httpx.get", return_value=mock_resp):
            try:
                tool.execute()
                assert False, "expected RuntimeError"
            except RuntimeError:
                pass
