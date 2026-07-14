from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from vinu_simulator.clients.features_client import FeaturesClient
from vinu_simulator.clients.price_client import PriceClient
from vinu_simulator.clients.strategy_client import StrategyClient
from vinu_simulator.config import load_config
from vinu_simulator.engine.custom_sim import simulate_custom as _run_custom_sim
from vinu_simulator.engine.metrics import compute_performance_metrics, periods_per_year_for_interval
from vinu_simulator.engine.simulator import WeightSimulator
from vinu_simulator.engine.strategies import BaseStrategy
from vinu_simulator.models.simulation import SimulationConfig, SimulationInput, SimulationResult
from vinu_simulator.server.schemas import CustomSimulateRequest, RunSummary, SimulateRequest
from vinu_simulator.storage.meta import MetaStorage
from vinu_simulator.storage.results import ResultStorage

LOG = logging.getLogger(__name__)


class SimulatorService:
    def __init__(self, config: Any | None = None):
        self._config = config or load_config()
        self._result_storage = ResultStorage(self._config.data_root)
        self._meta_storage = MetaStorage(
            self._config.data_root / "simulator_meta.db"
        )
        self._strategy_client = StrategyClient(self._config.strategy_api_url)
        self._price_client = PriceClient(self._config.stock_api_url)
        self._features_client = FeaturesClient(self._config.features_api_url)

    def simulate(self, req: SimulateRequest) -> SimulationResult:
        if req.dry_run:
            LOG.info("DRY RUN: simulate(%s) — skipping execution", req.strategy_name)
            result = SimulationResult(
                run_id="dry_run",
                strategy_name=req.strategy_name,
                timestamp=datetime.now(timezone.utc),
                metrics={"total_return": 0.0, "sharpe_ratio": 0.0, "max_drawdown": 0.0, "win_rate": 0.0, "cagr": 0.0, "total_return_pct": 0.0},
                portfolio_values=[],
                trades=[],
                benchmark_metrics={},
            )
            return result

        start_date = req.start_date or "2020-01-01"
        end_date = req.end_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")

        weight_signals = self._strategy_client.get_weights(
            req.strategy_name,
            from_ts=int(pd.Timestamp(start_date).timestamp()),
            to_ts=int(pd.Timestamp(end_date).timestamp()),
        )
        if weight_signals.empty:
            raise ValueError(
                f"No weight data found for strategy '{req.strategy_name}' "
                f"in range {start_date} to {end_date}"
            )

        tickers = weight_signals.columns.tolist()
        price_data, volume_data = self._price_client.get_price_and_volume(
            tickers, start_date, end_date
        )
        if price_data.empty:
            raise ValueError(f"No price data found for tickers {tickers}")

        sim_config = SimulationConfig(
            strategy_name=req.strategy_name,
            start_date=start_date,
            end_date=end_date,
            initial_capital=req.initial_capital if req.initial_capital is not None else self._config.initial_capital,
            transaction_cost_pct=req.transaction_cost_pct if req.transaction_cost_pct is not None else self._config.transaction_cost_pct,
            slippage_pct=req.slippage_pct if req.slippage_pct is not None else self._config.slippage_pct,
            slippage_model=req.slippage_model,
            benchmark_tickers=tuple(req.benchmark_tickers) if req.benchmark_tickers else self._config.benchmark_tickers,
            allow_short=req.allow_short,
            deviation_threshold=req.deviation_threshold if req.deviation_threshold is not None else self._config.deviation_threshold,
        )

        inp = SimulationInput(
            strategy_name=req.strategy_name,
            weight_signals=weight_signals,
            price_data=price_data,
            config=sim_config,
            volume_data=volume_data,
        )

        simulator = WeightSimulator(sim_config)
        result = simulator.run(inp)

        benchmark_metrics = self._compute_benchmark_metrics(
            price_data, sim_config
        )
        result.benchmark_metrics = benchmark_metrics

        self._result_storage.save(result)
        self._meta_storage.insert_run(
            run_id=result.run_id,
            strategy_name=result.strategy_name,
            timestamp=result.timestamp,
            config={
                "strategy_name": sim_config.strategy_name,
                "start_date": sim_config.start_date,
                "end_date": sim_config.end_date,
                "initial_capital": sim_config.initial_capital,
                "transaction_cost_pct": sim_config.transaction_cost_pct,
                "slippage_pct": sim_config.slippage_pct,
                "slippage_model": sim_config.slippage_model,
                "allow_short": sim_config.allow_short,
                "deviation_threshold": sim_config.deviation_threshold,
            },
            metrics=result.metrics,
            benchmark_metrics=benchmark_metrics,
            equity_points=len(result.portfolio_values),
            trade_count=len(result.trades),
        )

        return result

    def simulate_custom(self, req: CustomSimulateRequest) -> SimulationResult:
        start_date = req.start_date
        end_date = req.end_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")

        namespace: dict[str, Any] = {}
        try:
            exec(req.strategy_code, namespace)
        except Exception as e:
            raise ValueError(f"Failed to compile strategy code: {e}") from e

        strategy_class = namespace.get(req.class_name)
        if strategy_class is None:
            raise ValueError(
                f"Class '{req.class_name}' not found in provided strategy code"
            )
        if not (isinstance(strategy_class, type) and issubclass(strategy_class, BaseStrategy)):
            raise ValueError(
                f"'{req.class_name}' must be a subclass of BaseStrategy"
            )

        # /candles supports an `indicators` param that merges indicator columns
        # directly into each row server-side — the separate features-api client
        # below hits a route (/indicators/{symbol}) that only ever returns a
        # single latest-value snapshot, not a historical series, so it can't
        # supply what generate_weights() needs across the backtest window.
        requested_indicators = ["sma_20", "sma_50", "rsi_14"]
        ohclv_data = self._price_client.get_ohclv(
            req.symbols, start_date, end_date,
            resolution=req.interval, indicators=requested_indicators,
        )
        missing = [s for s in req.symbols if s not in ohclv_data or ohclv_data[s].empty]
        if missing:
            LOG.warning("No OHLCV data for symbols: %s — proceeding with available data", missing)

        indicator_data: dict[str, pd.DataFrame] = {}
        for sym in req.symbols:
            df = ohclv_data.get(sym)
            if df is None or df.empty:
                continue
            available = [c for c in requested_indicators if c in df.columns]
            if available:
                indicator_data[sym] = df[available]

        sim_config = SimulationConfig(
            strategy_name=req.class_name,
            start_date=start_date,
            end_date=end_date,
            initial_capital=req.initial_capital if req.initial_capital is not None else self._config.initial_capital,
            transaction_cost_pct=req.transaction_cost_pct if req.transaction_cost_pct is not None else self._config.transaction_cost_pct,
            slippage_pct=req.slippage_pct if req.slippage_pct is not None else self._config.slippage_pct,
            slippage_model=req.slippage_model,
            benchmark_tickers=tuple(req.benchmark_tickers) if req.benchmark_tickers else self._config.benchmark_tickers,
            allow_short=req.allow_short,
            deviation_threshold=req.deviation_threshold if req.deviation_threshold is not None else self._config.deviation_threshold,
            interval=req.interval,
        )

        result = _run_custom_sim(
            strategy_class=strategy_class,
            symbols=req.symbols,
            ohclv_data=ohclv_data,
            sim_config=sim_config,
            indicator_data=indicator_data,
        )

        all_prices = []
        for sym in req.symbols:
            if sym in ohclv_data and not ohclv_data[sym].empty:
                all_prices.append(ohclv_data[sym]["close"])
        if all_prices:
            price_df = pd.concat(all_prices, axis=1)
            price_df.columns = [s for s in req.symbols
                                if s in ohclv_data and not ohclv_data[s].empty]
            benchmark_metrics = self._compute_benchmark_metrics(price_df, sim_config)
        else:
            benchmark_metrics = {}
        result.benchmark_metrics = benchmark_metrics

        self._result_storage.save(result)
        self._meta_storage.insert_run(
            run_id=result.run_id,
            strategy_name=result.strategy_name,
            timestamp=result.timestamp,
            config={
                "strategy_name": sim_config.strategy_name,
                "start_date": sim_config.start_date,
                "end_date": sim_config.end_date,
                "initial_capital": sim_config.initial_capital,
                "transaction_cost_pct": sim_config.transaction_cost_pct,
                "slippage_pct": sim_config.slippage_pct,
                "slippage_model": sim_config.slippage_model,
                "allow_short": sim_config.allow_short,
                "deviation_threshold": sim_config.deviation_threshold,
            },
            metrics=result.metrics,
            benchmark_metrics=benchmark_metrics,
            equity_points=len(result.portfolio_values),
            trade_count=len(result.trades),
        )

        return result

    def _compute_benchmark_metrics(
        self,
        price_data: pd.DataFrame,
        config: SimulationConfig,
    ) -> dict[str, dict[str, float]]:
        benchmark_metrics: dict[str, dict[str, float]] = {}
        for ticker in config.benchmark_tickers:
            if ticker not in price_data.columns:
                continue
            prices = price_data[ticker].dropna()
            if len(prices) < 2:
                continue
            values = prices / prices.iloc[0] * config.initial_capital
            returns = values.pct_change().dropna()
            bm = compute_performance_metrics(
                values, returns,
                periods_per_year=periods_per_year_for_interval(config.interval),
            )
            benchmark_metrics[ticker] = bm
        return benchmark_metrics

    def get_result(self, run_id: str) -> dict[str, Any] | None:
        meta = self._meta_storage.get_run(run_id)
        if meta is None:
            return None
        equity_df = self._result_storage.load_equity(run_id)
        trades = self._result_storage.load_trades(run_id)
        meta["equity"] = (
            equity_df.to_dict(orient="records") if not equity_df.empty else []
        )
        meta["trades"] = [
            {
                "date": t.date.isoformat() if hasattr(t.date, "isoformat") else str(t.date),
                "symbol": t.symbol,
                "side": t.side,
                "shares": t.shares,
                "price": t.price,
                "cost": t.cost,
                "weight_before": t.weight_before,
                "weight_after": t.weight_after,
            }
            for t in trades
        ]
        return meta

    def get_equity(self, run_id: str) -> list[dict[str, Any]] | None:
        meta = self._meta_storage.get_run(run_id)
        if meta is None:
            return None
        df = self._result_storage.load_equity(run_id)
        if df.empty:
            return []
        # Match get_weights' date format (date-only string) — otherwise callers
        # joining the two endpoints on `date` silently get zero matches, since
        # this would default to a full ISO datetime string instead.
        df["date"] = df["date"].dt.strftime("%Y-%m-%d") if hasattr(df["date"], "dt") else df["date"].astype(str)
        return df.to_dict(orient="records")

    def get_weights(self, run_id: str) -> list[dict[str, Any]] | None:
        meta = self._meta_storage.get_run(run_id)
        if meta is None:
            return None
        df = self._result_storage.load_weights(run_id)
        if df.empty:
            return []
        df["date"] = df["date"].astype(str)
        return df.to_dict(orient="records")

    def get_trades(self, run_id: str) -> list[dict[str, Any]] | None:
        meta = self._meta_storage.get_run(run_id)
        if meta is None:
            return None
        trades = self._result_storage.load_trades(run_id)
        return [
            {
                "date": t.date.isoformat() if hasattr(t.date, "isoformat") else str(t.date),
                "symbol": t.symbol,
                "side": t.side,
                "shares": t.shares,
                "price": t.price,
                "cost": t.cost,
                "weight_before": t.weight_before,
                "weight_after": t.weight_after,
            }
            for t in trades
        ]

    def list_runs(self, strategy_name: str | None = None) -> list[RunSummary]:
        runs = self._meta_storage.list_runs(strategy_name)
        return [
            RunSummary(
                run_id=r["run_id"],
                strategy_name=r["strategy_name"],
                timestamp=r["timestamp"],
                metrics=r["metrics"],
                benchmark_metrics=r["benchmark_metrics"],
                trade_count=r["trade_count"],
                equity_points=r["equity_points"],
            )
            for r in runs
        ]

    def delete_run(self, run_id: str) -> bool:
        meta_deleted = self._meta_storage.delete_run(run_id)
        storage_deleted = self._result_storage.delete(run_id)
        return meta_deleted or storage_deleted

    def delete_runs(self, strategy_name: str | None = None) -> int:
        runs = self._meta_storage.list_runs(strategy_name)
        for r in runs:
            self._result_storage.delete(r["run_id"])
        return self._meta_storage.delete_runs(strategy_name)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self) -> None:
        self._strategy_client.close()
        self._price_client.close()
        self._meta_storage.close()


