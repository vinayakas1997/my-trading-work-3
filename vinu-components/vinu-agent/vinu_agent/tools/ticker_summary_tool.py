import json
from typing import Any

from ..agent.tools import BaseTool


class GetTickerSummaryTool(BaseTool):
    name = "get_ticker_summary"
    description = (
        "Read the Summary Agent's stored per-ticker angle synthesis -- the durable output of "
        "the screener team's own job (see storage/ticker_summaries.py). Use this to see 'what "
        "does the data already say about this ticker' without re-running angle synthesis."
    )
    parameters = {
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "description": "Stock symbol"},
        },
        "required": ["symbol"],
    }
    is_readonly = True
    _ticker_summary_store: Any = None

    def execute(self, **kwargs: Any) -> str:
        if self._ticker_summary_store is None:
            return json.dumps({"status": "error", "error": "ticker_summary_store not configured"})
        symbol = kwargs["symbol"]
        summary = self._ticker_summary_store.get_summary(symbol)
        if summary is None:
            return json.dumps({"status": "not_found", "symbol": symbol.upper()})
        return json.dumps({
            "status": "ok",
            "symbol": summary.ticker,
            "summary": summary.summary,
            "angles_with_data": summary.angles_with_data,
            "angle_count": summary.angle_count,
            "source_run_id": summary.source_run_id,
            "updated_at": summary.updated_at,
        })
