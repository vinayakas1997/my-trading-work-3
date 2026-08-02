import json
from ..agent.tools import BaseTool


class QueryMemoryTool(BaseTool):
    name = "query_memory"
    description = (
        "Search the unified agent memory across research runs, simulation results, "
        "price data, news articles, and stored findings. Use this to recall what the "
        "agent already knows about a symbol before starting new work."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search text (can be a symbol, concept, or question)",
            },
            "symbol": {
                "type": "string",
                "description": "Filter by stock symbol (optional)",
            },
            "source": {
                "type": "string",
                "description": "Filter by source: research, simulator, stock_price, news, agent (optional)",
                "enum": ["", "research", "simulator", "stock_price", "news", "agent"],
            },
            "memory_type": {
                "type": "string",
                "description": "Filter by type: research_run, strategy_artifact, simulation_run, price_summary, news_article, finding (optional)",
            },
            "limit": {
                "type": "integer",
                "description": "Max results to return (default: 15, max: 50)",
            },
        },
        "required": ["query"],
    }
    is_readonly = True

    def __init__(self):
        self._unified_memory = None

    def execute(self, **kwargs) -> str:
        memory = getattr(self, "_unified_memory", None)
        if memory is None:
            return json.dumps({"status": "error", "error": "Unified memory not available"})
        try:
            results = memory.search(
                query=kwargs.get("query", ""),
                symbol=kwargs.get("symbol"),
                source=kwargs.get("source") or None,
                memory_type=kwargs.get("memory_type") or None,
                limit=min(kwargs.get("limit", 15), 50),
            )
            return json.dumps({
                "status": "ok",
                "count": len(results),
                "results": [r.to_dict() for r in results],
            }, default=str)
        except Exception as exc:
            return json.dumps({"status": "error", "error": str(exc)})
