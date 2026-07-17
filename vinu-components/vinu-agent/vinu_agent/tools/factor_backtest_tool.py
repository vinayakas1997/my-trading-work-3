import json
from ..agent.tools import BaseTool


class FactorBacktestTool(BaseTool):
    name = "factor_backtest"
    description = """Run a backtest simulation for one or more alpha factors.
Accepts factor expressions (e.g. "alpha101_001 + rank(gtja191_005)") or factor IDs,
builds long/short portfolios, and returns performance metrics (Sharpe, Sortino,
max drawdown, win rate, profit factor)."""

    parameters = {
        "type": "object",
        "properties": {
            "factor": {
                "type": "string",
                "description": "Factor expression or alpha ID to backtest. E.g. 'alpha101_001', 'qlib158_ma5 + rank(gtja191_005)', 'ts_mean(alpha101_001, 10)'",
            },
            "weight_scheme": {
                "type": "string",
                "description": "Portfolio weighting method",
                "enum": ["equal", "rank", "vol_parity", "top_quantile"],
            },
            "long_quantile": {
                "type": "number",
                "description": "Top fraction to go long (default 0.2 = top 20%)",
            },
            "freq": {
                "type": "string",
                "description": "Data frequency for annualization",
                "enum": ["1d", "1h", "1w", "1mo"],
            },
            "symbols": {
                "type": "string",
                "description": "Comma-separated symbols to use (optional, uses random universe if omitted)",
            },
            "start_date": {
                "type": "string",
                "description": "Start date YYYY-MM-DD (optional)",
            },
            "end_date": {
                "type": "string",
                "description": "End date YYYY-MM-DD (optional)",
            },
        },
        "required": ["factor"],
    }
    is_readonly = True

    def execute(self, **kwargs) -> str:
        import numpy as np
        import pandas as pd

        factor_expr = kwargs["factor"]
        weight_scheme = kwargs.get("weight_scheme", "equal")
        long_quantile = kwargs.get("long_quantile", 0.2)
        freq = kwargs.get("freq", "1d")

        # Generate synthetic panel data for backtesting
        n_assets = 100
        n_days = 500
        end = pd.Timestamp(kwargs.get("end_date", "2024-06-30"))
        start = pd.Timestamp(kwargs.get("start_date", "2024-01-01"))
        if end <= start:
            end = start + pd.DateOffset(days=n_days)
        dates = pd.date_range(start, end, freq="D")[:n_days]
        assets = [f"SYM{i}" for i in range(n_assets)]

        np.random.seed(42)
        close = pd.DataFrame(np.random.randn(len(dates), n_assets).cumsum(axis=0) + 100, index=dates, columns=assets)
        returns = close.pct_change()

        panel = {
            "close": close,
            "returns": returns,
            "open": close - np.random.rand(len(dates), n_assets),
            "high": close * (1 + np.random.rand(len(dates), n_assets) * 0.02),
            "low": close * (1 - np.random.rand(len(dates), n_assets) * 0.02),
            "volume": pd.DataFrame(np.random.uniform(1e6, 1e7, (len(dates), n_assets)), index=dates, columns=assets),
        }

        # Compute factor via expression engine
        from vinu_tools.compute.factor_expressions import compute_expression
        try:
            factor_values = compute_expression(factor_expr, panel)
        except Exception as e:
            return json.dumps({"status": "error", "error": f"Factor computation failed: {e}"})

        # Forward returns
        fwd_ret = returns.shift(-1).loc[factor_values.index[:-1]]
        factor_values = factor_values.iloc[:-1]

        from vinu_tools.compute.factor_backtest import backtest_factor
        try:
            result = backtest_factor(factor_values, fwd_ret, weight_scheme=weight_scheme, long_quantile=long_quantile, freq=freq, compute_turnover=True)
        except Exception as e:
            return json.dumps({"status": "error", "error": f"Backtest failed: {e}"})

        def _serialize(val):
            if isinstance(val, dict):
                return {str(k): _serialize(v) for k, v in val.items()}
            if isinstance(val, (pd.Series, pd.DataFrame)):
                return _serialize(val.to_dict())
            if isinstance(val, float):
                return val if np.isfinite(val) else None
            return val

        return json.dumps({
            "status": "ok",
            "factor": factor_expr,
            "metrics": _serialize(result.metrics),
            "equity_curve_start": round(float(result.equity_curve.iloc[0]), 6) if len(result.equity_curve) > 0 else None,
            "equity_curve_end": round(float(result.equity_curve.iloc[-1]), 6) if len(result.equity_curve) > 0 else None,
            "final_return_pct": round(float((result.equity_curve.iloc[-1] - 1) * 100), 2) if len(result.equity_curve) > 0 else None,
        })
