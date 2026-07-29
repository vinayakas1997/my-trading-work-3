from ..agent.tools import BaseTool


class ResearchTool(BaseTool):
    name = "run_research"
    description = (
        "Run the full multi-iteration research loop for a trading idea: generates "
        "candidate strategy code, backtests it, applies a risk critic, and refines "
        "until PASS/STOP/max-iterations. Use dry_run=true first for a cheap sanity "
        "check before committing to a full run."
    )
    parameters = {
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
    }
    is_readonly = False

    def __init__(self):
        self._services_config = {}

    def execute(self, **kwargs) -> str:
        import httpx

        url = self._services_config.get("vinu_research", "http://localhost:8087")
        payload = {
            "user_idea": kwargs["idea"],
            "symbol": kwargs["symbol"],
            "from_date": kwargs["from_date"],
            "to_date": kwargs["to_date"],
        }
        if kwargs.get("indicators"):
            payload["indicators"] = [
                k.strip().lower() for k in kwargs["indicators"].split(",") if k.strip()
            ]
        if kwargs.get("initial_capital") is not None:
            payload["initial_capital"] = kwargs["initial_capital"]
        if kwargs.get("universe"):
            payload["universe"] = [
                t.strip().upper() for t in kwargs["universe"].split(",") if t.strip()
            ]
        if kwargs.get("dry_run"):
            payload["dry_run"] = True

        resp = httpx.post(f"{url}/run", json=payload, timeout=600)
        resp.raise_for_status()
        return resp.text
