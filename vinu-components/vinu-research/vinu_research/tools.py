from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx
import pandas as pd

from vinu_lib.client import ResilientClient
from vinu_research.benchmark import compute_benchmark_comparison as _compute_benchmark_comparison
from vinu_research.benchmark import compute_benchmark_returns_metrics as _compute_benchmark_returns_metrics
from vinu_research.config import ResearchConfig, load_config
from vinu_research.models import BacktestMetrics, BacktestResult

LOG = logging.getLogger(__name__)


class ResearchTools:
    def __init__(self, config: ResearchConfig | None = None):
        self._config = config or load_config()
        self._features_client = ResilientClient(
            self._config.features_api_url, "vinu-features",
            timeout=60.0, max_retries=3, circuit_breaker_threshold=3,
        )
        self._simulator_client = ResilientClient(
            self._config.simulator_api_url, "vinu-simulator",
            timeout=120.0, max_retries=2, circuit_breaker_threshold=3,
        )
        self._correlation_client = ResilientClient(
            self._config.correlation_api_url, "vinu-correlation",
            timeout=60.0, max_retries=3, circuit_breaker_threshold=3,
        )
        self._stock_client = ResilientClient(
            self._config.stock_price_api_url, "vinu-stock-price",
            timeout=30.0, max_retries=2, circuit_breaker_threshold=3,
        )

    async def close(self) -> None:
        await self._features_client.close()
        await self._simulator_client.close()
        await self._correlation_client.close()
        await self._stock_client.close()

    async def get_indicators(
        self,
        symbol: str,
        kinds: list[str],
        from_ts: int | None = None,
        to_ts: int | None = None,
        interval: str = "1d",
    ) -> pd.DataFrame | None:
        params: dict[str, Any] = {
            "kinds": ",".join(kinds),
            "interval": interval,
        }
        if from_ts is not None:
            params["from"] = from_ts
        if to_ts is not None:
            params["to"] = to_ts
        try:
            data = await self._features_client.get(
                f"/indicators/{symbol.upper()}",
                params=params,
            )
        except Exception as e:
            LOG.warning("get_indicators(%s, %s) failed: %s", symbol, kinds, e)
            return None
        if not isinstance(data, list):
            LOG.warning("get_indicators(%s, %s): unexpected response type %s", symbol, kinds, type(data).__name__)
            return None
        if not data:
            return None
        df = pd.DataFrame(data)
        df["ts"] = pd.to_datetime(df["ts"], unit="s")
        df = df.set_index("ts").sort_index()
        drop_cols = [c for c in ["symbol"] if c in df.columns]
        df = df.drop(columns=drop_cols, errors="ignore")
        return df

    async def run_backtest(
        self,
        strategy_code: str,
        strategy_class_name: str,
        symbols: list[str],
        from_date: str,
        to_date: str,
        indicators: list[str] | None = None,
        initial_capital: float | None = None,
        transaction_cost_pct: float | None = None,
        slippage_pct: float | None = None,
        allow_short: bool = True,
    ) -> BacktestResult | None:
        body: dict[str, Any] = {
            "strategy_code": strategy_code,
            "strategy_class_name": strategy_class_name,
            "symbols": symbols,
            "start_date": from_date,
            "end_date": to_date,
            "allow_short": allow_short,
        }
        if initial_capital is not None:
            body["initial_capital"] = initial_capital
        if transaction_cost_pct is not None:
            body["transaction_cost_pct"] = transaction_cost_pct
        if slippage_pct is not None:
            body["slippage_pct"] = slippage_pct
        if indicators is not None:
            body["indicators"] = indicators
        try:
            data = await self._simulator_client.post(
                "/simulate/custom",
                json=body,
            )
        except Exception as exc:
            raise RuntimeError(f"Backtest failed: {exc}") from exc
        if data is None:
            LOG.warning("run_backtest returned None (simulator down)")
            return None
        required = ["run_id", "strategy_name", "metrics", "trade_count", "equity_points"]
        missing = [k for k in required if k not in data]
        if missing:
            LOG.warning("run_backtest response missing keys: %s", missing)
            return None
        return BacktestResult(
            run_id=data["run_id"],
            strategy_name=data["strategy_name"],
            metrics=BacktestMetrics.from_dict(data["metrics"]),
            benchmark_metrics=data.get("benchmark_metrics", {}),
            trade_count=data["trade_count"],
            equity_points=data["equity_points"],
            raw=data,
        )

    async def get_story(
        self,
        symbol: str,
        from_ts: int | None = None,
        to_ts: int | None = None,
    ) -> dict[str, Any] | None:
        params: dict[str, Any] = {}
        if from_ts is not None:
            params["from"] = str(from_ts)
        if to_ts is not None:
            params["to"] = str(to_ts)
        try:
            resp = await self._correlation_client.get(
                f"/story/{symbol.upper()}",
                params=params,
            )
            return resp.get("data") if isinstance(resp, dict) else resp
        except Exception as e:
            LOG.warning("get_story(%s) failed: %s", symbol, e)
            return None

    async def get_drawdowns(
        self,
        symbol: str,
        from_ts: int | None = None,
        to_ts: int | None = None,
    ) -> dict[str, Any] | None:
        params: dict[str, Any] = {}
        if from_ts is not None:
            params["from"] = str(from_ts)
        if to_ts is not None:
            params["to"] = str(to_ts)
        try:
            return await self._correlation_client.get(
                f"/drawdown/{symbol.upper()}",
                params=params,
            )
        except Exception as e:
            LOG.warning("get_drawdowns(%s) failed: %s", symbol, e)
            return None

    async def get_correlation(
        self,
        symbol: str,
        from_ts: int | None = None,
        to_ts: int | None = None,
    ) -> dict[str, Any] | None:
        params: dict[str, Any] = {}
        if from_ts is not None:
            params["from"] = str(from_ts)
        if to_ts is not None:
            params["to"] = str(to_ts)
        try:
            return await self._correlation_client.get(
                f"/correlation/{symbol.upper()}",
                params=params,
            )
        except Exception as e:
            LOG.warning("get_correlation(%s) failed: %s", symbol, e)
            return None

    async def get_benchmark_data(
        self,
        symbol: str,
        from_date: str,
        to_date: str,
    ) -> pd.Series | None:
        """Fetch benchmark close prices and return daily returns series."""
        from_ts = int(pd.Timestamp(from_date).timestamp())
        to_ts = int(pd.Timestamp(to_date).timestamp())
        try:
            data = await self._stock_client.get(
                f"/query/{symbol.upper()}",
                params={"from": from_ts, "to": to_ts, "interval": "1d"},
            )
        except Exception as e:
            LOG.warning("get_benchmark_data(%s) failed: %s", symbol, e)
            return None
        if not isinstance(data, dict):
            return None
        close_prices = data.get("close")
        timestamps = data.get("timestamp")
        if close_prices is None or timestamps is None:
            return None
        prices = pd.Series(close_prices, index=pd.to_datetime(timestamps)).sort_index()
        if len(prices) < 2:
            return None
        returns = prices.pct_change().dropna()
        return returns

    async def fetch_equity_returns(self, run_id: str) -> pd.Series | None:
        """Fetch equity curve for a completed run and return daily returns."""
        try:
            data = await self._simulator_client.get(f"/results/{run_id}/equity")
        except Exception as e:
            LOG.warning("fetch_equity_returns(%s) failed: %s", run_id, e)
            return None
        if not isinstance(data, list) or len(data) < 2:
            return None
        df = pd.DataFrame(data)
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date")
        returns = df["portfolio_value"].pct_change().dropna()
        return returns

    @staticmethod
    def compute_benchmark_returns_metrics(daily_returns: pd.Series) -> dict[str, float]:
        return _compute_benchmark_returns_metrics(daily_returns)

    @staticmethod
    def compute_benchmark_comparison(
        strategy_returns: pd.Series,
        benchmark_returns: pd.Series,
    ) -> dict[str, float]:
        return _compute_benchmark_comparison(strategy_returns, benchmark_returns)


def timestamps_from_dates(from_date: str, to_date: str) -> tuple[int, int]:
    from_ts = int(pd.Timestamp(from_date).timestamp())
    to_ts = int(pd.Timestamp(to_date).timestamp())
    return from_ts, to_ts
