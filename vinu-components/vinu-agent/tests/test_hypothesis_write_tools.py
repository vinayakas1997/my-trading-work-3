import json
from unittest.mock import MagicMock, patch

import pytest

from vinu_agent.tools.hypothesis_write_tools import AddHypothesisEvidenceTool, CreateHypothesisTool
from vinu_research.hypothesis_registry import HypothesisRegistry
from vinu_research.models import Hypothesis, HypothesisStatus


def _create_tool(services_config: dict | None = None) -> CreateHypothesisTool:
    tool = CreateHypothesisTool()
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


class TestCreateHypothesisToolInProcess:
    def test_writes_real_hypothesis_and_returns_matching_shape(self, hypothesis_registry) -> None:
        tool = _create_tool()
        with patch("vinu_agent.broker.research_link.get_hypothesis_registry", return_value=hypothesis_registry):
            result = json.loads(tool.execute(title="t", thesis="th", symbol="aapl", strategy_type="crossover"))

        assert result["title"] == "t"
        assert result["thesis"] == "th"
        assert result["universe"] == ["AAPL"]
        assert result["strategy_type"] == "crossover"
        stored = hypothesis_registry.get(result["hypothesis_id"])
        assert stored is not None
        assert stored.thesis == "th"

    def test_falls_back_to_http_when_in_process_raises(self) -> None:
        tool = _create_tool({"vinu_research": "http://research-api:8087"})
        mock_resp = MagicMock()
        mock_resp.text = '{"hypothesis_id": "hyp_abc"}'
        with _force_in_process_unavailable(), patch("httpx.post", return_value=mock_resp) as mock_post:
            result = tool.execute(title="t", thesis="th", symbol="aapl", strategy_type="crossover")
        args, kwargs = mock_post.call_args
        assert args[0] == "http://research-api:8087/research/hypotheses"
        assert result == '{"hypothesis_id": "hyp_abc"}'


class TestCreateHypothesisToolHttpFallback:
    def test_uses_configured_service_url_and_prefix(self) -> None:
        tool = _create_tool({"vinu_research": "http://research-api:8087"})
        mock_resp = MagicMock()
        mock_resp.text = '{"hypothesis_id": "hyp_abc"}'
        with _force_in_process_unavailable(), patch("httpx.post", return_value=mock_resp) as mock_post:
            result = tool.execute(title="t", thesis="th", symbol="aapl", strategy_type="crossover")
        args, kwargs = mock_post.call_args
        assert args[0] == "http://research-api:8087/research/hypotheses"
        payload = kwargs["json"]
        assert payload == {"title": "t", "thesis": "th", "universe": ["AAPL"], "strategy_type": "crossover"}
        assert result == '{"hypothesis_id": "hyp_abc"}'

    def test_falls_back_to_default_url(self) -> None:
        tool = _create_tool()
        mock_resp = MagicMock()
        mock_resp.text = "{}"
        with _force_in_process_unavailable(), patch("httpx.post", return_value=mock_resp) as mock_post:
            tool.execute(title="t", thesis="th")
        args, _ = mock_post.call_args
        assert args[0] == "http://localhost:8087/research/hypotheses"

    def test_optional_fields_omitted_when_not_given(self) -> None:
        tool = _create_tool()
        mock_resp = MagicMock()
        mock_resp.text = "{}"
        with _force_in_process_unavailable(), patch("httpx.post", return_value=mock_resp) as mock_post:
            tool.execute(title="t", thesis="th")
        _, kwargs = mock_post.call_args
        payload = kwargs["json"]
        assert "universe" not in payload
        assert "strategy_type" not in payload

    def test_raises_on_http_error(self) -> None:
        tool = _create_tool()
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = RuntimeError("boom")
        with _force_in_process_unavailable(), patch("httpx.post", return_value=mock_resp):
            try:
                tool.execute(title="t", thesis="th")
                assert False, "expected RuntimeError"
            except RuntimeError:
                pass


def _evidence_tool(services_config: dict | None = None) -> AddHypothesisEvidenceTool:
    tool = AddHypothesisEvidenceTool()
    tool._services_config = services_config or {}
    return tool


class TestAddHypothesisEvidenceToolInProcess:
    def test_writes_real_evidence_to_existing_hypothesis(self, hypothesis_registry) -> None:
        h = Hypothesis.create(title="t", thesis="th")
        hypothesis_registry.create(h)
        tool = _evidence_tool()

        with patch("vinu_agent.broker.research_link.get_hypothesis_registry", return_value=hypothesis_registry):
            result = json.loads(tool.execute(
                hypothesis_id=h.hypothesis_id, metric="sharpe", value=1.2, conclusion="supports",
                reasoning="widened window revealed a peak", run_id=5, iteration=2,
            ))

        assert result["evidence_count"] == 1
        stored = hypothesis_registry.get(h.hypothesis_id)
        assert stored.evidence[0].metric == "sharpe"
        assert stored.evidence[0].run_id == 5

    def test_unknown_hypothesis_falls_back_to_http(self, hypothesis_registry) -> None:
        tool = _evidence_tool({"vinu_research": "http://research-api:8087"})
        mock_resp = MagicMock()
        mock_resp.text = '{"evidence_count": 1}'
        with patch(
            "vinu_agent.broker.research_link.get_hypothesis_registry", return_value=hypothesis_registry,
        ), patch("httpx.post", return_value=mock_resp) as mock_post:
            result = tool.execute(hypothesis_id="does_not_exist", metric="sharpe", value=1.0, conclusion="supports")
        mock_post.assert_called_once()
        assert result == '{"evidence_count": 1}'


class TestAddHypothesisEvidenceToolHttpFallback:
    def test_uses_configured_service_url_and_prefix(self) -> None:
        tool = _evidence_tool({"vinu_research": "http://research-api:8087"})
        mock_resp = MagicMock()
        mock_resp.text = '{"evidence_count": 1}'
        with _force_in_process_unavailable(), patch("httpx.post", return_value=mock_resp) as mock_post:
            result = tool.execute(
                hypothesis_id="hyp_abc", metric="sharpe", value=1.2, conclusion="supports",
                reasoning="widened window revealed a peak", run_id=5, iteration=2,
            )
        args, kwargs = mock_post.call_args
        assert args[0] == "http://research-api:8087/research/hypotheses/hyp_abc/evidence"
        payload = kwargs["json"]
        assert payload == {
            "metric": "sharpe", "value": 1.2, "conclusion": "supports",
            "reasoning": "widened window revealed a peak", "run_id": 5, "iteration": 2,
        }
        assert result == '{"evidence_count": 1}'

    def test_optional_fields_omitted_when_not_given(self) -> None:
        tool = _evidence_tool()
        mock_resp = MagicMock()
        mock_resp.text = "{}"
        with _force_in_process_unavailable(), patch("httpx.post", return_value=mock_resp) as mock_post:
            tool.execute(hypothesis_id="hyp_abc", metric="sharpe", value=1.2, conclusion="supports")
        _, kwargs = mock_post.call_args
        payload = kwargs["json"]
        assert "reasoning" not in payload
        assert "run_id" not in payload
        assert "iteration" not in payload

    def test_raises_on_http_error(self) -> None:
        tool = _evidence_tool()
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = RuntimeError("boom")
        with _force_in_process_unavailable(), patch("httpx.post", return_value=mock_resp):
            try:
                tool.execute(hypothesis_id="hyp_abc", metric="sharpe", value=1.0, conclusion="supports")
                assert False, "expected RuntimeError"
            except RuntimeError:
                pass
