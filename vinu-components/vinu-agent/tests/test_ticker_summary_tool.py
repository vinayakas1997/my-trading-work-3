import json
import tempfile
from pathlib import Path

import pytest

from vinu_agent.storage.ticker_summaries import TickerSummaryStore
from vinu_agent.tools.ticker_summary_tool import GetTickerSummaryTool


@pytest.fixture
def store():
    path = Path(tempfile.mktemp(suffix=".db"))
    s = TickerSummaryStore(path)
    yield s
    s.close()
    path.unlink(missing_ok=True)


def _tool(store) -> GetTickerSummaryTool:
    tool = GetTickerSummaryTool()
    tool._ticker_summary_store = store
    return tool


class TestGetTickerSummaryTool:
    def test_no_store_configured_errors(self) -> None:
        result = json.loads(GetTickerSummaryTool().execute(symbol="AAPL"))
        assert result["status"] == "error"

    def test_unknown_symbol_returns_not_found(self, store) -> None:
        result = json.loads(_tool(store).execute(symbol="AAPL"))
        assert result["status"] == "not_found"
        assert result["symbol"] == "AAPL"

    def test_known_symbol_returns_real_summary(self, store) -> None:
        store.upsert_summary("AAPL", "12 of 28 angles have data...", angles_with_data=12, angle_count=28, source_run_id="run-1")
        result = json.loads(_tool(store).execute(symbol="aapl"))
        assert result["status"] == "ok"
        assert result["symbol"] == "AAPL"
        assert result["summary"] == "12 of 28 angles have data..."
        assert result["angles_with_data"] == 12
        assert result["source_run_id"] == "run-1"
