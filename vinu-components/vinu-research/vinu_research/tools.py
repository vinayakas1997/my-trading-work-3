from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx
import pandas as pd

from vinu_research.config import ResearchConfig, load_config
from vinu_research.models import BacktestMetrics, BacktestResult

LOG = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_BACKOFF = 1.0


class ResearchTools:
    def __init__(self, config: ResearchConfig | None = None):
        self._config = config or load_config()
        self._http = httpx.AsyncClient(timeout=60.0)

    async def close(self) -> None:
        await self._http.aclose()

    async def _request(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> httpx.Response:
        last_exc: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                resp = await self._http.request(method, url, **kwargs)
                resp.raise_for_status()
                return resp
            except httpx.HTTPStatusError as e:
                LOG.warning("HTTP %d on %s %s (attempt %d/%d)",
                            e.response.status_code, method, url,
                            attempt + 1, MAX_RETRIES)
                last_exc = e
                if e.response.status_code < 500:
                    raise
            except httpx.TimeoutException as e:
                LOG.warning("Timeout on %s %s (attempt %d/%d)",
                            method, url, attempt + 1, MAX_RETRIES)
                last_exc = e
            except httpx.RequestError as e:
                LOG.warning("Request failed on %s %s (attempt %d/%d): %s",
                            method, url, attempt + 1, MAX_RETRIES, e)
                last_exc = e
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_BACKOFF * (2 ** attempt))
        raise RuntimeError(f"Request failed after {MAX_RETRIES} attempts: {last_exc}") from last_exc

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
        url = f"{self._config.features_api_url}/indicators/{symbol.upper()}"
        try:
            resp = await self._request("GET", url, params=params)
            data = resp.json()
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
        url = f"{self._config.simulator_api_url}/simulate/custom"
        try:
            resp = await self._request("POST", url, json=body)
            data = resp.json()
        except Exception as exc:
            raise RuntimeError(f"Backtest failed: {exc}") from exc
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
        url = f"{self._config.correlation_api_url}/story/{symbol.upper()}"
        try:
            resp = await self._request("GET", url, params=params)
            return resp.json()
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
        url = f"{self._config.correlation_api_url}/drawdown/{symbol.upper()}"
        try:
            resp = await self._request("GET", url, params=params)
            return resp.json()
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
        url = f"{self._config.correlation_api_url}/correlation/{symbol.upper()}"
        try:
            resp = await self._request("GET", url, params=params)
            return resp.json()
        except Exception as e:
            LOG.warning("get_correlation(%s) failed: %s", symbol, e)
            return None


def timestamps_from_dates(from_date: str, to_date: str) -> tuple[int, int]:
    from_ts = int(pd.Timestamp(from_date).timestamp())
    to_ts = int(pd.Timestamp(to_date).timestamp())
    return from_ts, to_ts
