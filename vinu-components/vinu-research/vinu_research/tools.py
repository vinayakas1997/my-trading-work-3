from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx
import pandas as pd

from vinu_lib.client import ResilientClient
from vinu_research.angle_context import build_angle_context
from vinu_research.benchmark import compute_benchmark_comparison as _compute_benchmark_comparison
from vinu_research.benchmark import compute_benchmark_returns_metrics as _compute_benchmark_returns_metrics
from vinu_research.config import ResearchConfig, load_config
from vinu_research.models import BacktestMetrics, BacktestResult, HypothesisStatus

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
            self._config.correlation_api_url, "vinu-initial-analysis",
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
        interval: str | None = None,
        run_validation: bool = True,
    ) -> BacktestResult | None:
        body: dict[str, Any] = {
            "strategy_code": strategy_code,
            "class_name": strategy_class_name,
            "symbols": symbols,
            "start_date": from_date,
            "end_date": to_date,
            "allow_short": allow_short,
            "run_validation": run_validation,
        }
        if initial_capital is not None:
            body["initial_capital"] = initial_capital
        if transaction_cost_pct is not None:
            body["transaction_cost_pct"] = transaction_cost_pct
        if slippage_pct is not None:
            body["slippage_pct"] = slippage_pct
        if indicators is not None:
            body["indicators"] = indicators
        if interval is not None:
            body["interval"] = interval
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

    async def get_angle_rows(self, angle_name: str, symbol: str) -> list[dict[str, Any]]:
        """Fetch all stored rows for one initial-analysis angle (read-only endpoint)."""
        try:
            resp = await self._correlation_client.get(
                f"/angle/{angle_name}/{symbol.upper()}",
            )
            if isinstance(resp, dict):
                data = resp.get("data")
                return data if isinstance(data, list) else []
        except Exception as e:
            LOG.warning("get_angle_rows(%s, %s) failed: %s", angle_name, symbol, e)
        return []

    async def get_angle_context(self, symbol: str, interval: str = "1d") -> dict[str, Any]:
        """Compact context from the deterministic angles for the risk critic / LLM.

        Reads trend_lifecycle, trend_session_structure, and news_price_causality
        and reduces them to a small dict (see angle_context.build_angle_context).
        Returns {} when the angles have not been run for this symbol.
        """
        trend_rows, session_rows, causality_rows = await asyncio.gather(
            self.get_angle_rows("trend_lifecycle", symbol),
            self.get_angle_rows("trend_session_structure", symbol),
            self.get_angle_rows("news_price_causality", symbol),
        )
        return build_angle_context(trend_rows, session_rows, causality_rows, interval=interval)

    async def get_feature_snapshot(
        self,
        symbol: str,
        recipe: str = "sma_20,sma_50,rsi_14",
    ) -> dict[str, Any] | None:
        """Fetch a snapshot of computed features for a symbol from vinu-tools.

        Calls the features-api /features/{symbol} endpoint (the same one
        vinu-strategy's WeightPipeline uses). Returns the raw response dict
        (column names and latest values) or None if unavailable.
        """
        params = {}
        if recipe:
            params["indicators"] = recipe
        try:
            resp = await self._features_client.get(
                f"/features/{symbol.upper()}",
                params=params,
            )
            if isinstance(resp, dict):
                return resp
        except Exception as e:
            LOG.warning("get_feature_snapshot(%s, recipe=%s) failed: %s", symbol, recipe, e)
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
                f"/candles/{symbol.upper()}",
                params={"from": from_ts, "to": to_ts, "interval": "1d", "adjusted": True},
            )
        except Exception as e:
            LOG.warning("get_benchmark_data(%s) failed: %s", symbol, e)
            return None
        if not isinstance(data, dict):
            return None
        records = data.get("data")
        if not records:
            return None
        prices = pd.Series(
            [r["close"] for r in records],
            index=pd.to_datetime([r["bar_ts"] for r in records], unit="s"),
        ).sort_index()
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

    async def fetch_weights(self, run_id: str) -> list[dict[str, Any]] | None:
        """Fetch weights history for a completed run."""
        try:
            return await self._simulator_client.get(f"/results/{run_id}/weights")
        except Exception as e:
            LOG.warning("fetch_weights(%s) failed: %s", run_id, e)
            return None

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


# ── Research Autopilot Tools (Feature 2) ──────────────────────────────

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from vinu_research.hypothesis_registry import HypothesisRegistry
from vinu_research.models import Goal


def run_autopilot(
    hypothesis_id: str,
    registry: HypothesisRegistry | None = None,
) -> dict[str, Any]:
    reg = registry or HypothesisRegistry()
    hypothesis = reg.get(hypothesis_id)
    if hypothesis is None:
        raise ValueError(f"Hypothesis {hypothesis_id} not found")

    now = datetime.now(timezone.utc).isoformat()
    raw = f"goal:{hypothesis_id}:{now}"
    goal_id = f"goal_{hashlib.sha256(raw.encode()).hexdigest()[:12]}"

    goal = Goal(
        goal_id=goal_id,
        hypothesis_id=hypothesis_id,
        objective=f"Test hypothesis: {hypothesis.title}",
        criteria=[
            "Sharpe ratio > 1.0",
            "Max drawdown > -20%",
            "Win rate > 40%",
        ],
        status="active",
    )

    return {
        "goal_id": goal.goal_id,
        "hypothesis_id": hypothesis_id,
        "hypothesis_title": hypothesis.title,
        "hypothesis_thesis": hypothesis.thesis,
        "objective": goal.objective,
        "criteria": goal.criteria,
        "status": goal.status,
        "universe": hypothesis.universe,
        "created_at": now,
    }


def generate_backtest_config(
    hypothesis_id: str,
    start_date: str,
    end_date: str,
    registry: HypothesisRegistry | None = None,
    output_dir: str | None = None,
) -> str:
    reg = registry or HypothesisRegistry()
    hypothesis = reg.get(hypothesis_id)
    if hypothesis is None:
        raise ValueError(f"Hypothesis {hypothesis_id} not found")

    run_dir = Path(output_dir or Path.home() / ".vinu" / "runs" / f"autopilot_{hypothesis_id}")
    run_dir.mkdir(parents=True, exist_ok=True)

    config = {
        "run_id": f"autopilot_{hypothesis_id}",
        "hypothesis_id": hypothesis_id,
        "title": hypothesis.title,
        "thesis": hypothesis.thesis,
        "universe": hypothesis.universe,
        "start_date": start_date,
        "end_date": end_date,
        "interval": "1d",
        "initial_capital": 1_000_000.0,
        "transaction_cost_pct": 0.001,
        "slippage_pct": 0.0005,
        "allow_short": True,
        "signal_definition": hypothesis.signal_definition or "",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    config_path = run_dir / "config.json"
    tmp = None
    try:
        fd, tmp = tempfile.mkstemp(suffix=".tmp", prefix="config_", dir=str(run_dir))
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
            f.flush()
            os.fsync(fd)
        os.replace(tmp, str(config_path))
    finally:
        if tmp is not None and os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except OSError:
                pass

    return str(config_path)


def scaffold_signal_engine(
    hypothesis_id: str,
    registry: HypothesisRegistry | None = None,
    output_dir: str | None = None,
) -> str:
    reg = registry or HypothesisRegistry()
    hypothesis = reg.get(hypothesis_id)
    if hypothesis is None:
        raise ValueError(f"Hypothesis {hypothesis_id} not found")

    run_dir = Path(output_dir or Path.home() / ".vinu" / "runs" / f"autopilot_{hypothesis_id}")
    run_dir.mkdir(parents=True, exist_ok=True)

    sig_def = hypothesis.signal_definition or "Custom signal"
    universe_str = ", ".join(hypothesis.universe) if hypothesis.universe else "symbol"

    code = f'''"""Signal Engine: {hypothesis.title}

Hypothesis: {hypothesis.thesis}
Signal Definition: {sig_def}
Universe: {universe_str}
Generated: {datetime.now(timezone.utc).isoformat()}
"""

from typing import Any
import pandas as pd
import numpy as np


class SignalEngine:
    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {{}}

    def compute_signals(self, data: pd.DataFrame) -> pd.Series:
        """
        Compute trading signals from price/feature data.

        Parameters
        ----------
        data : pd.DataFrame
            OHLCV data with columns: open, high, low, close, volume

        Returns
        -------
        pd.Series
            Trading signals: +1 (long), -1 (short), 0 (neutral)
        """
        # TODO: Implement signal logic based on hypothesis
        # {sig_def}
        signals = pd.Series(0.0, index=data.index)
        return signals
'''
    sig_path = run_dir / "signal_engine.py"
    sig_path.write_text(code, encoding="utf-8")
    return str(sig_path)


def link_autopilot_backtest(
    hypothesis_id: str,
    run_dir: str,
    registry: HypothesisRegistry | None = None,
) -> dict[str, Any]:
    reg = registry or HypothesisRegistry()
    hypothesis = reg.get(hypothesis_id)
    if hypothesis is None:
        raise ValueError(f"Hypothesis {hypothesis_id} not found")

    run_dir_path = Path(run_dir)
    run_card_path = run_dir_path / "run_card.json"

    result = {
        "hypothesis_id": hypothesis_id,
        "run_dir": run_dir,
        "run_card_found": False,
        "metrics": {},
        "hypothesis_status": hypothesis.status.value,
    }

    if run_card_path.exists():
        try:
            run_card = json.loads(run_card_path.read_text(encoding="utf-8"))
            result["run_card_found"] = True
            result["metrics"] = run_card.get("metrics", {})

            reg.link_backtest(hypothesis_id, str(run_card_path))
            linked = reg.get(hypothesis_id)
            if linked is not None:
                linked.status = HypothesisStatus.testing
                reg.update(linked)
                result["hypothesis_status"] = "testing"
        except (json.JSONDecodeError, OSError) as exc:
            LOG.warning("Failed to read run_card.json at %s: %s", run_card_path, exc)

    return result
