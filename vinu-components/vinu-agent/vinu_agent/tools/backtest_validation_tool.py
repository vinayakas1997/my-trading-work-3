import json

from ..agent.tools import BaseTool


class BacktestValidationTool(BaseTool):
    name = "get_backtest_validation"
    description = (
        "Read the full statistical validation verdict for a specific backtest "
        "result — Monte Carlo permutation p-value, block bootstrap, price-path "
        "resample, walk-forward consistency, bootstrap CI, BCa CI, and placebo "
        "test, combined into an overall pass/fail with reasons. This is the "
        "real, already-computed statistical evidence for whether a result is "
        "trustworthy, not just its top-line Sharpe/drawdown. Use the backtest's "
        "run_id (a string, distinct from a research run's integer id) from a "
        "prior simulate/research call."
    )
    parameters = {
        "run_id": {"type": "string", "description": "Backtest run ID (from a simulate or research call's result)"},
    }
    is_readonly = True

    def __init__(self):
        self._services_config = {}

    def execute(self, **kwargs) -> str:
        import httpx

        url = self._services_config.get("vinu_simulator", "http://localhost:8085")
        # The /metrics sub-route strips the validation block, so this hits the
        # full /results/{run_id} route and discards equity/trades locally —
        # keeps this tool's output small without needing a new simulator route.
        resp = httpx.get(
            f"{url}/simulator/results/{kwargs['run_id']}",
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return json.dumps({
            "run_id": kwargs["run_id"],
            "metrics": data.get("metrics"),
            "benchmark_metrics": data.get("benchmark_metrics"),
            "trade_count": len(data.get("trades") or []),
            "validation": data.get("validation"),
        })
