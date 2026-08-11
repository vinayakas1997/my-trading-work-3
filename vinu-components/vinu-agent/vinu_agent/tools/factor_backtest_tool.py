import json
import time
from datetime import datetime, timezone

from ..agent.tools import BaseTool


def _date_to_epoch(date_str: str) -> int:
    return int(time.mktime(time.strptime(date_str, "%Y-%m-%d")))


def _iso_to_epoch(iso: str) -> int:
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return int(dt.timestamp())


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
                "description": (
                    "Comma-separated real symbols to fetch OHLCV for and backtest "
                    "against (e.g. 'AAPL,MSFT,GOOGL'). Recommended. Omit only for "
                    "exploratory factor research against synthetic random-walk "
                    "data -- the response's data_source field will say "
                    "'synthetic' in that case."
                ),
            },
            "start_date": {
                "type": "string",
                "description": "Start date YYYY-MM-DD (optional, defaults to 2 years back when symbols is given)",
            },
            "end_date": {
                "type": "string",
                "description": "End date YYYY-MM-DD (optional)",
            },
        },
        "required": ["factor"],
    }
    is_readonly = True
    _as_of: str | None = None

    def __init__(self):
        self._services_config = {}

    def execute(self, **kwargs) -> str:
        import numpy as np
        import pandas as pd

        factor_expr = kwargs["factor"]
        weight_scheme = kwargs.get("weight_scheme", "equal")
        long_quantile = kwargs.get("long_quantile", 0.2)
        freq = kwargs.get("freq", "1d")
        symbols_raw = str(kwargs.get("symbols") or "").strip()

        if symbols_raw:
            panel, meta = self._build_real_panel(symbols_raw, kwargs)
            if panel is None:
                return json.dumps(meta)
        else:
            panel = self._build_synthetic_panel(kwargs)
            meta = {
                "data_source": "synthetic",
                "n_synthetic_assets": len(panel["close"].columns),
                "note": (
                    "No symbols provided -- backtested against synthetic "
                    "random-walk data for exploratory research only. Pass "
                    "`symbols` to backtest against real OHLCV data."
                ),
            }

        close = panel["close"]
        returns = panel["returns"]

        # Compute factor via expression engine
        from vinu_tools.compute.factors.expressions import compute_expression
        try:
            factor_values = compute_expression(factor_expr, panel)
        except Exception as e:
            return json.dumps({"status": "error", "error": f"Factor computation failed: {e}"})

        # Forward returns
        fwd_ret = returns.shift(-1).loc[factor_values.index[:-1]]
        factor_values = factor_values.iloc[:-1]

        from vinu_tools.compute.bench.backtest import backtest_factor
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
            **meta,
            "metrics": _serialize(result.metrics),
            "equity_curve_start": round(float(result.equity_curve.iloc[0]), 6) if len(result.equity_curve) > 0 else None,
            "equity_curve_end": round(float(result.equity_curve.iloc[-1]), 6) if len(result.equity_curve) > 0 else None,
            "final_return_pct": round(float((result.equity_curve.iloc[-1] - 1) * 100), 2) if len(result.equity_curve) > 0 else None,
        })

    def _build_real_panel(self, symbols_raw: str, kwargs: dict):
        """Fetch real OHLCV from vinu-stock-price and build the close/open/
        high/low/volume/returns panel compute_expression/backtest_factor
        need. Returns (panel_dict, meta_dict) on success, or (None,
        error_payload) if fewer than 2 symbols end up with usable data --
        never silently falls back to synthetic data when the caller
        explicitly asked for real symbols."""
        import httpx
        import pandas as pd

        symbols = sorted({s.strip().upper() for s in symbols_raw.split(",") if s.strip()})[:50]
        url = self._services_config.get("vinu_stock_price", "http://localhost:8081")

        as_of_epoch = _iso_to_epoch(self._as_of) if self._as_of else int(time.time())
        end_epoch = _date_to_epoch(kwargs["end_date"]) if kwargs.get("end_date") else as_of_epoch
        start_epoch = (
            _date_to_epoch(kwargs["start_date"])
            if kwargs.get("start_date")
            else end_epoch - 730 * 86400
        )
        if self._as_of and end_epoch > as_of_epoch:
            end_epoch = as_of_epoch
        if start_epoch >= end_epoch:
            start_epoch = end_epoch - 730 * 86400

        per_symbol_rows: dict[str, list[dict]] = {}
        failed: list[dict] = []
        with httpx.Client(timeout=30.0) as client:
            for sym in symbols:
                try:
                    resp = client.get(
                        f"{url}/stock/candles/{sym}",
                        params={"from": start_epoch, "to": end_epoch, "interval": "1d"},
                    )
                    resp.raise_for_status()
                    rows = resp.json().get("data", [])
                    if not rows:
                        failed.append({"symbol": sym, "reason": "no data returned"})
                        continue
                    per_symbol_rows[sym] = rows
                except Exception as exc:
                    failed.append({"symbol": sym, "reason": str(exc)})

        if len(per_symbol_rows) < 2:
            return None, {
                "status": "error",
                "error": (
                    "Could not fetch real OHLCV data for enough symbols to run a "
                    "cross-sectional factor backtest (need at least 2)."
                ),
                "symbols_failed": failed,
            }

        def _field_frame(field: str) -> pd.DataFrame:
            series = {}
            for sym, rows in per_symbol_rows.items():
                idx = pd.to_datetime([r["bar_ts"] for r in rows], unit="s", utc=True)
                series[sym] = pd.Series([r[field] for r in rows], index=idx)
            return pd.DataFrame(series).sort_index().ffill()

        close = _field_frame("close")
        panel = {
            "close": close,
            "returns": close.pct_change(),
            "open": _field_frame("open"),
            "high": _field_frame("high"),
            "low": _field_frame("low"),
            "volume": _field_frame("volume"),
        }
        meta = {
            "data_source": "real",
            "symbols_used": sorted(per_symbol_rows.keys()),
            "symbols_failed": failed,
            "date_range": {"start_ts": start_epoch, "end_ts": end_epoch},
        }
        return panel, meta

    def _build_synthetic_panel(self, kwargs: dict):
        import numpy as np
        import pandas as pd

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

        return {
            "close": close,
            "returns": returns,
            "open": close - np.random.rand(len(dates), n_assets),
            "high": close * (1 + np.random.rand(len(dates), n_assets) * 0.02),
            "low": close * (1 - np.random.rand(len(dates), n_assets) * 0.02),
            "volume": pd.DataFrame(np.random.uniform(1e6, 1e7, (len(dates), n_assets)), index=dates, columns=assets),
        }
