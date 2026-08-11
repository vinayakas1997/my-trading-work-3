import json
from unittest.mock import MagicMock, patch

import pytest

from vinu_agent.tools.symbol_research_state_tool import SymbolResearchStateTool
from vinu_research.storage.sqlite_backend import ResearchStorage


def _tool(services_config: dict | None = None) -> SymbolResearchStateTool:
    tool = SymbolResearchStateTool()
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


class TestSymbolResearchStateToolInProcess:
    def test_reads_real_exhaustion_state(self, research_storage) -> None:
        research_storage.touch_catalog_validated_ts("AAPL")  # creates the catalog row
        research_storage.exhaust_symbol("AAPL")
        tool = _tool()
        with patch("vinu_agent.broker.research_link.get_research_storage", return_value=research_storage):
            result = json.loads(tool.execute(symbol="AAPL"))
        assert result["symbol"] == "AAPL"
        assert result["exhausted"] is True

    def test_not_exhausted_by_default(self, research_storage) -> None:
        tool = _tool()
        with patch("vinu_agent.broker.research_link.get_research_storage", return_value=research_storage):
            result = json.loads(tool.execute(symbol="MSFT"))
        assert result["exhausted"] is False
        assert result["catalog_entry"] is None

    def test_falls_back_to_http_when_in_process_raises(self) -> None:
        tool = _tool({"vinu_research": "http://research-api:8087"})
        mock_resp = MagicMock()
        mock_resp.text = '{"symbol": "AAPL", "exhausted": false, "catalog_entry": null}'
        with _force_in_process_unavailable(), patch("httpx.get", return_value=mock_resp) as mock_get:
            result = tool.execute(symbol="AAPL")
        mock_get.assert_called_once()
        assert result == '{"symbol": "AAPL", "exhausted": false, "catalog_entry": null}'


class TestSymbolResearchStateToolHttpFallback:
    def test_uses_configured_service_url_and_prefix(self) -> None:
        tool = _tool({"vinu_research": "http://research-api:8087"})
        mock_resp = MagicMock()
        mock_resp.text = '{"symbol": "AAPL", "exhausted": false, "catalog_entry": null}'
        with _force_in_process_unavailable(), patch("httpx.get", return_value=mock_resp) as mock_get:
            result = tool.execute(symbol="AAPL")
        args, _ = mock_get.call_args
        assert args[0] == "http://research-api:8087/research/symbols/AAPL/state"
        assert result == '{"symbol": "AAPL", "exhausted": false, "catalog_entry": null}'

    def test_falls_back_to_default_url(self) -> None:
        tool = _tool()
        mock_resp = MagicMock()
        mock_resp.text = "{}"
        with _force_in_process_unavailable(), patch("httpx.get", return_value=mock_resp) as mock_get:
            tool.execute(symbol="MSFT")
        args, _ = mock_get.call_args
        assert args[0] == "http://localhost:8087/research/symbols/MSFT/state"

    def test_raises_on_http_error(self) -> None:
        tool = _tool()
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = RuntimeError("boom")
        with _force_in_process_unavailable(), patch("httpx.get", return_value=mock_resp):
            try:
                tool.execute(symbol="AAPL")
                assert False, "expected RuntimeError"
            except RuntimeError:
                pass
