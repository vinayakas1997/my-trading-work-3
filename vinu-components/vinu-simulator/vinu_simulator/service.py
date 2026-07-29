from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from vinu_simulator.clients.features_client import FeaturesClient
from vinu_simulator.clients.price_client import PriceClient
from vinu_simulator.clients.strategy_client import StrategyClient
from vinu_simulator.config import load_config
from vinu_lib.debug import sync_timer
from vinu_simulator.engine.custom_sim import simulate_custom as _run_custom_sim
from vinu_simulator.engine.metrics import compute_performance_metrics, periods_per_year_for_interval
from vinu_simulator.engine.run_card import write_run_card
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

    @staticmethod
    def _compute_config_hash(params: dict[str, Any]) -> str:
        raw = json.dumps(params, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()

    def _reconstruct_result(self, row: dict[str, Any]) -> SimulationResult:
        """Build a SimulationResult from a cached MetaStorage row."""
        portfolio_values = self._result_storage.load_equity(row["run_id"])
        daily_returns = portfolio_values["daily_return"] if not portfolio_values.empty else pd.Series()
        prices = portfolio_values["portfolio_value"] if not portfolio_values.empty else pd.Series()
        trades = self._result_storage.load_trades(row["run_id"])
        return SimulationResult(
            run_id=row["run_id"],
            strategy_name=row["strategy_name"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            config=SimulationConfig(**row["config"]),
            metrics=row["metrics"],
            benchmark_metrics=row["benchmark_metrics"],
            portfolio_values=prices,
            daily_returns=daily_returns,
            weights_history=pd.DataFrame(),
            trades=trades,
            validation=row.get("validation"),
        )

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

        config_hash = self._compute_config_hash({
            "strategy_name": req.strategy_name,
            "start_date": req.start_date,
            "end_date": req.end_date,
            "initial_capital": req.initial_capital,
            "transaction_cost_pct": req.transaction_cost_pct,
            "slippage_pct": req.slippage_pct,
            "slippage_model": req.slippage_model,
            "benchmark_tickers": sorted(req.benchmark_tickers) if req.benchmark_tickers else None,
            "allow_short": req.allow_short,
            "deviation_threshold": req.deviation_threshold,
            "full_metrics": req.full_metrics,
            "run_validation": req.run_validation,
        })
        cached = self._meta_storage.get_run_by_config_hash(config_hash)
        if cached is not None:
            LOG.info("Cache hit for %s — returning cached result %s", req.strategy_name, cached["run_id"])
            return self._reconstruct_result(cached)

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
            full_metrics=req.full_metrics,
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

        validation = None
        attribution = None
        if req.run_validation:
            validation, attribution = self._run_validation_and_attribution(result, price_data)
        result.validation = validation

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
            config_hash=config_hash,
            validation=validation,
            symbols=list(weight_signals.columns),
        )

        run_dir = self._config.data_root / "simulations" / result.run_id[:2] / result.run_id
        write_run_card(
            run_dir=run_dir,
            run_id=result.run_id,
            config={
                "symbols": list(weight_signals.columns),
                "start_date": sim_config.start_date,
                "end_date": sim_config.end_date,
                "interval": sim_config.interval,
                "initial_capital": sim_config.initial_capital,
            },
            metrics=result.metrics,
            benchmark_metrics=benchmark_metrics,
            trade_count=len(result.trades),
            equity_points=len(result.portfolio_values),
            validation=validation,
            attribution=attribution,
        )

        return result

    def simulate_custom(self, req: CustomSimulateRequest) -> SimulationResult:
        with sync_timer(f"simulate_custom.{req.class_name}"):
            return self._simulate_custom_impl(req)

    def _simulate_custom_impl(self, req: CustomSimulateRequest) -> SimulationResult:
        from vinu_simulator.engine.ast_guard import validate_strategy_code
        violations = validate_strategy_code(req.strategy_code)
        if violations:
            raise ValueError(f"Strategy code failed security validation: {', '.join(violations)}")

        config_hash = self._compute_config_hash({
            "type": "custom",
            "strategy_code": req.strategy_code,
            "class_name": req.class_name,
            "symbols": sorted(req.symbols),
            "start_date": req.start_date,
            "end_date": req.end_date,
            "initial_capital": req.initial_capital,
            "transaction_cost_pct": req.transaction_cost_pct,
            "slippage_pct": req.slippage_pct,
            "slippage_model": req.slippage_model,
            "benchmark_tickers": sorted(req.benchmark_tickers) if req.benchmark_tickers else None,
            "allow_short": req.allow_short,
            "deviation_threshold": req.deviation_threshold,
            "interval": req.interval,
            "indicators": sorted(req.indicators) if req.indicators else None,
            "full_metrics": req.full_metrics,
            "run_validation": req.run_validation,
        })
        cached = self._meta_storage.get_run_by_config_hash(config_hash)
        if cached is not None:
            LOG.info("Cache hit for custom sim %s — returning cached result %s", req.class_name, cached["run_id"])
            return self._reconstruct_result(cached)

        start_date = req.start_date
        end_date = req.end_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Pre-pend required imports if the strategy code omits them
        # (e.g. LLM-generated code often ignores the prompt's import instruction).
        required_imports = (
            "from __future__ import annotations\n"
            "import pandas as pd\n"
            "import numpy as np\n"
            "from vinu_simulator.engine.strategies import BaseStrategy\n"
            "\n"
        )
        code = req.strategy_code
        if not code.startswith("from ") and not code.startswith("import "):
            code = required_imports + code

        namespace: dict[str, Any] = {}
        try:
            exec(code, namespace)
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
        requested_indicators = req.indicators or ["sma_20", "sma_50", "rsi_14"]
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
            full_metrics=req.full_metrics,
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
            price_df = pd.DataFrame()
            benchmark_metrics = {}
        result.benchmark_metrics = benchmark_metrics

        self._result_storage.save(result)

        validation = None
        attribution = None
        if req.run_validation:
            validation, attribution = self._run_validation_and_attribution(result, price_df)
        result.validation = validation

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
            config_hash=config_hash,
            validation=validation,
            symbols=list(req.symbols),
        )

        run_dir = self._config.data_root / "simulations" / result.run_id[:2] / result.run_id
        write_run_card(
            run_dir=run_dir,
            run_id=result.run_id,
            config={
                "symbols": req.symbols,
                "start_date": sim_config.start_date,
                "end_date": sim_config.end_date,
                "interval": sim_config.interval,
                "initial_capital": sim_config.initial_capital,
            },
            metrics=result.metrics,
            benchmark_metrics=benchmark_metrics,
            trade_count=len(result.trades),
            equity_points=len(result.portfolio_values),
            validation=validation,
            attribution=attribution,
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

    def get_result(self, run_id: str, *, load_data: bool = True) -> dict[str, Any] | None:
        meta = self._meta_storage.get_run(run_id)
        if meta is None:
            return None
        if load_data:
            equity_df = self._result_storage.load_equity(run_id)
            meta["equity"] = (
                equity_df.to_dict(orient="records") if not equity_df.empty else []
            )
            meta["trades"] = self._result_storage._trades_to_dicts(run_id)
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
        return self._result_storage._trades_to_dicts(run_id)

    def list_runs(
        self, strategy_name: str | None = None, symbol: str | None = None,
    ) -> list[RunSummary]:
        runs = self._meta_storage.list_runs(strategy_name, symbol)
        return [
            RunSummary(
                run_id=r["run_id"],
                strategy_name=r["strategy_name"],
                timestamp=r["timestamp"],
                metrics=r["metrics"],
                benchmark_metrics=r["benchmark_metrics"],
                trade_count=r["trade_count"],
                equity_points=r["equity_points"],
                validation=r.get("validation"),
                symbols=r.get("symbols", []),
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

    def _run_validation_and_attribution(
        self,
        result: SimulationResult,
        price_data: pd.DataFrame,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        from vinu_simulator.engine.validation import (
            monte_carlo_permutation, bootstrap_sharpe_ci, bootstrap_sharpe_ci_bca,
            placebo_test, walk_forward_consistency,
            block_bootstrap_permutation, price_path_resample, compute_validation_verdict,
        )
        from vinu_simulator.engine.attribution import by_symbol_stats, beta_regression, match_trades
        from vinu_simulator.engine.regime import classify_regime, per_regime_performance
        
        sim_config = result.config
        periods_per_year = periods_per_year_for_interval(sim_config.interval)
        
        # Validation
        round_trips = match_trades(result.trades)
        trade_pnls = [rt["pnl"] for rt in round_trips]
        
        mc_result = monte_carlo_permutation(
            trade_pnls=trade_pnls,
            actual_sharpe=result.metrics.get("sharpe_ratio", 0.0),
            initial_capital=sim_config.initial_capital,
        )
        
        bb_result = block_bootstrap_permutation(
            trade_pnls=trade_pnls,
            actual_sharpe=result.metrics.get("sharpe_ratio", 0.0),
            initial_capital=sim_config.initial_capital,
        )
        
        pr_result = price_path_resample(
            daily_returns=result.daily_returns,
            actual_sharpe=result.metrics.get("sharpe_ratio", 0.0),
        )
        
        bs_result = bootstrap_sharpe_ci(
            daily_returns=result.daily_returns,
            periods_per_year=periods_per_year,
        )
        
        bca_result = bootstrap_sharpe_ci_bca(
            daily_returns=result.daily_returns,
            periods_per_year=periods_per_year,
        )
        
        signal_dates = [pd.Timestamp(t.date) for t in result.trades if hasattr(t, "date")]
        placebo_result = placebo_test(
            strategy_returns=result.daily_returns,
            signal_dates=signal_dates,
            periods_per_year=periods_per_year,
        )
        
        wf_result = walk_forward_consistency(
            equity_curve=result.portfolio_values,
            periods_per_year=periods_per_year,
        )
        
        validation = {
            "monte_carlo": mc_result,
            "block_bootstrap": bb_result,
            "price_path": pr_result,
            "bootstrap": bs_result,
            "bca": bca_result,
            "placebo": placebo_result,
            "walk_forward": wf_result,
        }
        
        validation["verdict"] = compute_validation_verdict(validation)
        
        # Attribution
        symbol_attribution = by_symbol_stats(result.trades, round_trips=round_trips)
        
        benchmark_attribution = {}
        regime_attribution = {}
        
        for ticker in sim_config.benchmark_tickers:
            if ticker in price_data.columns:
                bench_prices = price_data[ticker].dropna()
                if len(bench_prices) >= 2:
                    bench_vals = bench_prices / bench_prices.iloc[0] * sim_config.initial_capital
                    bench_returns = bench_vals.pct_change().dropna()
                    
                    beta_reg = beta_regression(
                        strategy_returns=result.daily_returns,
                        benchmark_returns=bench_returns,
                        periods_per_year=periods_per_year,
                    )
                    if beta_reg:
                        benchmark_attribution[ticker] = beta_reg
                        
                    regimes = classify_regime(bench_returns)
                    regime_perf = per_regime_performance(result.daily_returns, regimes)
                    regime_attribution[ticker] = regime_perf
                    
        attribution = {
            "by_symbol": symbol_attribution,
            "by_benchmark": benchmark_attribution,
            "by_regime": regime_attribution,
        }
        
        return validation, attribution


