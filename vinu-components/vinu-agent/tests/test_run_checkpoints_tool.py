import json
from unittest.mock import MagicMock, patch

import pytest

from vinu_agent.tools.run_checkpoints_tool import RunCheckpointsTool
from vinu_research.storage.sqlite_backend import ResearchStorage


def _tool(services_config: dict | None = None) -> RunCheckpointsTool:
    tool = RunCheckpointsTool()
    tool._services_config = services_config or {}
    return tool


def _force_in_process_unavailable():
    return patch(
        "vinu_agent.broker.research_link.get_research_storage",
        side_effect=RuntimeError("not available"),
    )


@pytest.fixture
def research_storage(tmp_path) -> ResearchStorage:
    return ResearchStorage(tmp_path / "research_meta.db")


class TestRunCheckpointsToolInProcess:
    def test_lists_real_checkpoints(self, research_storage) -> None:
        research_storage.save_checkpoint(5, 1, code="c1", metrics={"sharpe": 1.0})
        research_storage.save_checkpoint(5, 2, code="c2", metrics={"sharpe": 1.2})
        tool = _tool()
        with patch("vinu_agent.broker.research_link.get_research_storage", return_value=research_storage):
            result = json.loads(tool.execute(run_id=5))
        assert result["run_id"] == 5
        assert result["count"] == 2

    def test_latest_only_returns_single_checkpoint(self, research_storage) -> None:
        research_storage.save_checkpoint(5, 1, code="c1")
        research_storage.save_checkpoint(5, 2, code="c2")
        tool = _tool()
        with patch("vinu_agent.broker.research_link.get_research_storage", return_value=research_storage):
            result = json.loads(tool.execute(run_id=5, latest_only=True))
        assert result["checkpoint"]["iteration"] == 2

    def test_falls_back_to_http_when_in_process_raises(self) -> None:
        tool = _tool({"vinu_research": "http://research-api:8087"})
        mock_resp = MagicMock()
        mock_resp.text = '{"run_id": 5, "count": 0, "checkpoints": []}'
        with _force_in_process_unavailable(), patch("httpx.get", return_value=mock_resp) as mock_get:
            result = tool.execute(run_id=5)
        mock_get.assert_called_once()
        assert result == '{"run_id": 5, "count": 0, "checkpoints": []}'


class TestRunCheckpointsToolHttpFallback:
    def test_uses_configured_service_url_and_prefix(self) -> None:
        tool = _tool({"vinu_research": "http://research-api:8087"})
        mock_resp = MagicMock()
        mock_resp.text = '{"run_id": 5, "count": 0, "checkpoints": []}'
        with _force_in_process_unavailable(), patch("httpx.get", return_value=mock_resp) as mock_get:
            result = tool.execute(run_id=5)
        args, kwargs = mock_get.call_args
        assert args[0] == "http://research-api:8087/research/runs/5/checkpoints"
        assert kwargs["params"] == {}
        assert result == '{"run_id": 5, "count": 0, "checkpoints": []}'

    def test_falls_back_to_default_url(self) -> None:
        tool = _tool()
        mock_resp = MagicMock()
        mock_resp.text = "{}"
        with _force_in_process_unavailable(), patch("httpx.get", return_value=mock_resp) as mock_get:
            tool.execute(run_id=1)
        args, _ = mock_get.call_args
        assert args[0] == "http://localhost:8087/research/runs/1/checkpoints"

    def test_passes_latest_only(self) -> None:
        tool = _tool()
        mock_resp = MagicMock()
        mock_resp.text = "{}"
        with _force_in_process_unavailable(), patch("httpx.get", return_value=mock_resp) as mock_get:
            tool.execute(run_id=1, latest_only=True)
        _, kwargs = mock_get.call_args
        assert kwargs["params"] == {"latest_only": True}

    def test_raises_on_http_error(self) -> None:
        tool = _tool()
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = RuntimeError("boom")
        with _force_in_process_unavailable(), patch("httpx.get", return_value=mock_resp):
            try:
                tool.execute(run_id=1)
                assert False, "expected RuntimeError"
            except RuntimeError:
                pass
