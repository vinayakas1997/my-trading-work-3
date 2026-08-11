import asyncio
import json
import logging

from ..agent.tools import BaseTool

LOG = logging.getLogger(__name__)


class ResearchTool(BaseTool):
    name = "run_research"
    description = (
        "Run the full multi-iteration research loop for a trading idea: generates "
        "candidate strategy code, backtests it, applies a risk critic, and refines "
        "until PASS/STOP/max-iterations. Use dry_run=true first for a cheap sanity "
        "check before committing to a full run."
    )
    parameters = {
        "type": "object",
        "properties": {
            "idea": {"type": "string", "description": "Research hypothesis or trading idea"},
            "symbol": {"type": "string", "description": "Stock symbol"},
            "from_date": {"type": "string", "description": "Start date YYYY-MM-DD"},
            "to_date": {"type": "string", "description": "End date YYYY-MM-DD"},
            "indicators": {
                "type": "string",
                "description": "Comma-separated indicator kinds to make available, e.g. 'sma_20,rsi_14' (optional)",
            },
            "initial_capital": {
                "type": "number",
                "description": "Starting capital for the backtest (optional, defaults to service config)",
            },
            "universe": {
                "type": "string",
                "description": "Comma-separated tickers to backtest as a portfolio alongside symbol, e.g. 'MSFT,GOOGL' (optional)",
            },
            "dry_run": {
                "type": "boolean",
                "description": "If true, validate inputs and return without running the full loop (optional, default false)",
            },
        },
        "required": ["idea", "symbol", "from_date", "to_date"],
    }
    is_readonly = False

    def __init__(self):
        self._services_config = {}

    def execute(self, **kwargs) -> str:
        indicators = (
            [k.strip().lower() for k in kwargs["indicators"].split(",") if k.strip()]
            if kwargs.get("indicators") else None
        )
        universe = (
            [t.strip().upper() for t in kwargs["universe"].split(",") if t.strip()]
            if kwargs.get("universe") else None
        )

        try:
            result = asyncio.run(self._run_in_process(
                user_idea=kwargs["idea"], symbol=kwargs["symbol"],
                from_date=kwargs["from_date"], to_date=kwargs["to_date"],
                indicators=indicators, initial_capital=kwargs.get("initial_capital"),
                universe=universe, dry_run=bool(kwargs.get("dry_run")),
            ))
            return json.dumps(result, default=str)
        except Exception as exc:
            LOG.debug("run_research: in-process run failed, falling back to HTTP: %s", exc)

        import httpx

        url = self._services_config.get("vinu_research", "http://localhost:8087")
        payload = {
            "user_idea": kwargs["idea"],
            "symbol": kwargs["symbol"],
            "from_date": kwargs["from_date"],
            "to_date": kwargs["to_date"],
        }
        if indicators:
            payload["indicators"] = indicators
        if kwargs.get("initial_capital") is not None:
            payload["initial_capital"] = kwargs["initial_capital"]
        if universe:
            payload["universe"] = universe
        if kwargs.get("dry_run"):
            payload["dry_run"] = True

        resp = httpx.post(f"{url}/research/run", json=payload, timeout=600)
        resp.raise_for_status()
        return resp.text

    async def _run_in_process(self, **kwargs) -> dict:
        from ..broker.research_link import get_research_service

        service = get_research_service()
        try:
            return await service.run_research(**kwargs)
        finally:
            await service.close()
