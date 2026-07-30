import json

from ..agent.tools import BaseTool


class RunSweepCandidateTool(BaseTool):
    name = "run_sweep_candidate"
    description = (
        "Run ONE backtest of a strategy at ONE specific set of numeric "
        "parameter values (e.g. SMA period=9, RSI threshold=25) and return "
        "the full result including the statistical validation block. This "
        "tool does not decide which values to try or when to stop — that "
        "adaptive reasoning is the caller's job, calling this repeatedly "
        "round by round. Two modes: (1) recipe mode — pass `recipe` (see "
        "list_sweep_recipes) and `params` as a JSON object with the full "
        "parameter set for this candidate. (2) base_code mode — pass "
        "`base_code` (an existing strategy's full source, e.g. from a prior "
        "iteration) plus `param_name`/`param_value` to vary exactly one "
        "already-present numeric parameter in it."
    )
    parameters = {
        "symbol": {"type": "string", "description": "Stock symbol"},
        "from_date": {"type": "string", "description": "Start date YYYY-MM-DD"},
        "to_date": {"type": "string", "description": "End date YYYY-MM-DD"},
        "recipe": {
            "type": "string",
            "description": "Recipe-mode: a built-in strategy template key (see list_sweep_recipes). Requires `params`.",
        },
        "params": {
            "type": "string",
            "description": "Recipe-mode: JSON object of the full parameter set for this candidate, e.g. '{\"fast_period\": 9, \"slow_period\": 40}'",
        },
        "base_code": {
            "type": "string",
            "description": "Base-code-mode: existing strategy source to vary one parameter of. Requires `param_name`/`param_value`.",
        },
        "param_name": {"type": "string", "description": "Base-code-mode: the parameter name to vary"},
        "param_value": {"type": "number", "description": "Base-code-mode: the new value for param_name"},
        "indicators": {
            "type": "string",
            "description": "Comma-separated indicator kinds to make available, e.g. 'sma_20,rsi_14' (optional)",
        },
        "initial_capital": {
            "type": "number",
            "description": "Starting capital for the backtest (optional, defaults to service config)",
        },
    }
    is_readonly = False

    def __init__(self):
        self._services_config = {}

    def execute(self, **kwargs) -> str:
        import httpx

        url = self._services_config.get("vinu_research", "http://localhost:8087")
        payload = {
            "symbol": kwargs["symbol"],
            "from_date": kwargs["from_date"],
            "to_date": kwargs["to_date"],
        }
        if kwargs.get("recipe"):
            payload["recipe"] = kwargs["recipe"]
            if kwargs.get("params"):
                payload["params"] = json.loads(kwargs["params"])
        if kwargs.get("base_code"):
            payload["base_code"] = kwargs["base_code"]
            if kwargs.get("param_name"):
                payload["param_name"] = kwargs["param_name"]
            if kwargs.get("param_value") is not None:
                payload["param_value"] = kwargs["param_value"]
        if kwargs.get("indicators"):
            payload["indicators"] = [
                k.strip().lower() for k in kwargs["indicators"].split(",") if k.strip()
            ]
        if kwargs.get("initial_capital") is not None:
            payload["initial_capital"] = kwargs["initial_capital"]

        resp = httpx.post(f"{url}/research/sweep/candidate", json=payload, timeout=180)
        resp.raise_for_status()
        return resp.text


class ListSweepRecipesTool(BaseTool):
    name = "list_sweep_recipes"
    description = (
        "List built-in strategy recipes available for run_sweep_candidate's "
        "recipe mode, each with its tunable parameter names and default "
        "values. Read this before picking a recipe + params."
    )
    parameters = {}
    is_readonly = True

    def __init__(self):
        self._services_config = {}

    def execute(self, **kwargs) -> str:
        import httpx

        url = self._services_config.get("vinu_research", "http://localhost:8087")
        resp = httpx.get(f"{url}/research/sweep/recipes", timeout=30)
        resp.raise_for_status()
        return resp.text
