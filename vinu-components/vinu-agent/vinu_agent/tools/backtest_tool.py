import json
from ..agent.tools import BaseTool


class BacktestTool(BaseTool):
    name = "run_backtest"
    description = (
        "Run a backtest for a trading strategy. The strategy_code must define a class "
        "(default name Strategy) that SUBCLASSES BaseStrategy (from "
        "vinu_simulator.engine.strategies import BaseStrategy -- pre-pended automatically "
        "if strategy_code has no top-level import/from line of its own) and overrides "
        "generate_weights(self, data) -> pd.Series. A bare `class Strategy:` with no base "
        "class is rejected by the real simulator. Returns metrics (sharpe, max_drawdown, "
        "total_return), trade count, run_id, and a `validation` block (Monte Carlo "
        "permutation, block-bootstrap, price-path resample, walk-forward consistency, "
        "bootstrap/BCa confidence intervals, combined into validation.verdict.passed/reasons) "
        "-- the real statistical evidence for whether this result reflects genuine edge or "
        "could easily be noise/overfit, always computed."
    )
    parameters = {
        "type": "object",
        "properties": {
            "strategy_code": {
                "type": "string",
                "description": (
                    "Python code defining a class(BaseStrategy) with a generate_weights "
                    "method, e.g. 'class Strategy(BaseStrategy):\\n    def generate_weights"
                    "(self, data):\\n        return pd.Series(...)'. pandas (pd), numpy (np), "
                    "and BaseStrategy are already in scope -- no import needed unless the "
                    "code itself starts with its own import/from line."
                ),
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
                "description": "Bar interval, lowercase only: 1m, 5m, 15m, 30m, 1h, 4h, 1d (default: 1d)",
            },
            "initial_capital": {
                "type": "number",
                "description": "Starting capital in USD (default: 100000)",
            },
            "indicators": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Indicator column names to merge into `data` before generate_weights "
                    "runs, e.g. ['sma_20', 'rsi_14']. Only these exact names are usable as "
                    "data['name'] inside your strategy -- ONLY: sma_5, sma_10, sma_20, "
                    "sma_50 (or any sma_N), rsi_14, macd, macd_signal, daily_return, "
                    "volatility_20d, adx_14. This is a smaller set than the full "
                    "list_available_features catalog -- other indicators from that catalog "
                    "(supertrend, cmf, aroon, bollinger, etc.) are not backtest-mergeable yet "
                    "and referencing them in code will fail. Defaults to "
                    "['sma_20', 'sma_50', 'rsi_14'] if omitted."
                ),
            },
        },
        "required": ["strategy_code", "symbol", "start_date", "end_date"],
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
            "interval": kwargs.get("interval", "1d"),
            "initial_capital": kwargs.get("initial_capital", 100000),
            "indicators": kwargs.get("indicators") or ["sma_20", "sma_50", "rsi_14"],
            # Always on: Monte Carlo permutation, block-bootstrap, price-path
            # resample, walk-forward consistency, bootstrap/BCa CI, placebo
            # test -- ~0.7s of real wall-clock cost (measured), returned
            # inline in this same response as `validation`, no separate call
            # needed. Was silently defaulting to off (the simulator's own
            # default), meaning risk_critic's PASS/STOP verdict had zero
            # statistical-overfitting evidence behind it -- top-line Sharpe
            # on one historical path only.
            "run_validation": True,
        }
        resp = httpx.post(
            f"{simulator_url}/simulator/simulate/custom",
            json=payload,
            timeout=120,
        )
        resp.raise_for_status()
        return resp.text
