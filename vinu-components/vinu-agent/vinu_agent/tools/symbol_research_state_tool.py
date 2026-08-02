from ..agent.tools import BaseTool


class SymbolResearchStateTool(BaseTool):
    name = "check_symbol_research_state"
    description = (
        "Check whether a symbol has been marked exhausted (too many failed "
        "research trials without a passing strategy) and see its cross-run "
        "trial history (lifetime trial count, best Sharpe ever achieved). Use "
        "this before starting a new research run on a symbol — if it's "
        "exhausted, a new run will return early without doing real work."
    )
    parameters = {
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "description": "Stock symbol"},
        },
        "required": ["symbol"],
    }
    is_readonly = True

    def __init__(self):
        self._services_config = {}

    def execute(self, **kwargs) -> str:
        import httpx

        url = self._services_config.get("vinu_research", "http://localhost:8087")
        resp = httpx.get(f"{url}/research/symbols/{kwargs['symbol']}/state", timeout=30)
        resp.raise_for_status()
        return resp.text
