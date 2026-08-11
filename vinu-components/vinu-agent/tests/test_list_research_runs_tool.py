import json
from unittest.mock import MagicMock, patch

import pytest

from vinu_agent.tools.list_research_runs_tool import ListResearchRunsTool
from vinu_research.storage.models import ResearchRunRecord
from vinu_research.storage.sqlite_backend import ResearchStorage


def _tool(services_config: dict | None = None) -> ListResearchRunsTool:
    tool = ListResearchRunsTool()
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


class TestListResearchRunsToolInProcess:
    def test_lists_real_runs(self, research_storage) -> None:
        research_storage.insert_run(ResearchRunRecord(user_idea="idea1", symbol="AAPL", from_date="2026-01-01", to_date="2026-02-01"))
        research_storage.insert_run(ResearchRunRecord(user_idea="idea2", symbol="MSFT", from_date="2026-01-01", to_date="2026-02-01"))
        tool = _tool()
        with patch("vinu_agent.broker.research_link.get_research_storage", return_value=research_storage):
            result = json.loads(tool.execute())
        assert result["count"] == 2
        symbols = {r["symbol"] for r in result["runs"]}
        assert symbols == {"AAPL", "MSFT"}

    def test_filters_by_symbol(self, research_storage) -> None:
        research_storage.insert_run(ResearchRunRecord(user_idea="idea1", symbol="AAPL", from_date="2026-01-01", to_date="2026-02-01"))
        research_storage.insert_run(ResearchRunRecord(user_idea="idea2", symbol="MSFT", from_date="2026-01-01", to_date="2026-02-01"))
        tool = _tool()
        with patch("vinu_agent.broker.research_link.get_research_storage", return_value=research_storage):
            result = json.loads(tool.execute(symbol="AAPL"))
        assert result["count"] == 1
        assert result["runs"][0]["symbol"] == "AAPL"

    def test_falls_back_to_http_when_in_process_raises(self) -> None:
        tool = _tool({"vinu_research": "http://research-api:8087"})
        mock_resp = MagicMock()
        mock_resp.text = '{"count": 0, "runs": []}'
        with _force_in_process_unavailable(), patch("httpx.get", return_value=mock_resp) as mock_get:
            result = tool.execute()
        mock_get.assert_called_once()
        assert result == '{"count": 0, "runs": []}'


class TestListResearchRunsToolHttpFallback:
    def test_uses_configured_service_url_and_params(self) -> None:
        tool = _tool({"vinu_research": "http://research-api:8087"})
        mock_resp = MagicMock()
        mock_resp.text = '{"count": 0, "runs": []}'
        with _force_in_process_unavailable(), patch("httpx.get", return_value=mock_resp) as mock_get:
            result = tool.execute(symbol="AAPL", status="done", limit=10)
        args, kwargs = mock_get.call_args
        assert args[0] == "http://research-api:8087/research/runs"
        assert kwargs["params"] == {"limit": 10, "symbol": "AAPL", "status": "done"}
        assert result == '{"count": 0, "runs": []}'

    def test_falls_back_to_default_url(self) -> None:
        tool = _tool()
        mock_resp = MagicMock()
        mock_resp.text = "{}"
        with _force_in_process_unavailable(), patch("httpx.get", return_value=mock_resp) as mock_get:
            tool.execute()
        args, kwargs = mock_get.call_args
        assert args[0] == "http://localhost:8087/research/runs"
        assert kwargs["params"] == {"limit": 50}

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
