import json
from ..agent.tools import BaseTool


class BacktestTool(BaseTool):
    name = "run_backtest"
    description = (
        "Run a backtest for a trading strategy. The strategy_code must define "
        "a class Strategy with a generate_weights(self, data) -> pd.Series method. "
        "Returns metrics (sharpe, max_drawdown, total_return) and trade count."
    )
    parameters = {
        "strategy_code": {
            "type": "string",
            "description": "Python code defining a Strategy class with generate_weights method",
        },
        "symbol": {
            "type": "string",
            "description": "Stock symbol (e.g., AAPL, 600519.SH, BTC-USDT)",
        },
        "start_date": {
            "type": "string",
            "description": "Start date in YYYY-MM-DD format",
        },
        "end_date": {
            "type": "string",
            "description": "End date in YYYY-MM-DD format",
        },
        "interval": {
            "type": "string",
            "description": "Bar interval: 1m, 5m, 15m, 1h, 1D (default: 1D)",
        },
        "initial_capital": {
            "type": "number",
            "description": "Starting capital in USD (default: 100000)",
        },
    }
    is_readonly = False

    def __init__(self):
        self._services_config = {}

    def execute(self, **kwargs) -> str:
        import httpx
        simulator_url = self._services_config.get(
            "vinu_simulator", "http://localhost:8085"
        )
        payload = {
            "strategy_code": kwargs["strategy_code"],
            "class_name": kwargs.get("class_name", "Strategy"),
            "symbols": [kwargs["symbol"]],
            "start_date": kwargs["start_date"],
            "end_date": kwargs["end_date"],
            "interval": kwargs.get("interval", "1D"),
            "initial_capital": kwargs.get("initial_capital", 100000),
        }
        resp = httpx.post(
            f"{simulator_url}/simulate/custom",
            json=payload,
            timeout=120,
        )
        resp.raise_for_status()
        return resp.text
