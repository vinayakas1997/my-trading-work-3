from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any

from vinu_strategy.clients.features_client import FeaturesClient
from vinu_strategy.clients.correlation_client import CorrelationClient
from vinu_strategy.config import VinuStrategyConfig
from vinu_strategy.engine.pipeline import WeightPipeline
from vinu_strategy.engine.registry import StrategyRegistry
from vinu_strategy.models.strategy import StrategyConfig, StrategyResult
from vinu_strategy.storage.meta import MetaStorage
from vinu_strategy.storage.weights import WeightStorage

LOG = logging.getLogger(__name__)

_MAX_WORKERS = 10


class StrategyService:
    def __init__(self, config: VinuStrategyConfig):
        self._config = config
        self._registry = StrategyRegistry(config.strategies_dir)
        self._pipeline = WeightPipeline()
        self._features_client = FeaturesClient(config.features_api_url)
        self._correlation_client = CorrelationClient(config.correlation_api_url)
        self._meta_storage = MetaStorage(config.data_root / "meta.db")
        self._weight_storage = WeightStorage(config.data_root)
        self._registry.load_all()
        self._sync_registry()

    def _sync_registry(self) -> None:
        for name, scfg in self._registry._strategies.items():
            self._meta_storage.register_strategy(name, scfg.description, scfg.schedule)

    def list_strategies(self) -> list[dict[str, Any]]:
        return self._meta_storage.get_registered_strategies()

    def get_strategy(self, name: str) -> StrategyConfig | None:
        return self._registry.get(name)

    def evaluate(
        self,
        strategy_name: str,
        symbols: list[str] | None = None,
        run_id: str | None = None,
    ) -> StrategyResult:
        config = self._registry.get(strategy_name)
        if config is None:
            raise ValueError(f"Unknown strategy: {strategy_name}")

        actual_run_id = run_id or f"{strategy_name}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        universe = self._resolve_universe(config, symbols)
        if not universe:
            LOG.warning("Empty universe for strategy '%s'", strategy_name)

        feature_signals: dict[str, dict[str, float]] = {}
        if config.features_required:
            with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as pool:
                fut_to_sym = {
                    pool.submit(self._features_client.get_features, sym, indicators=config.features_required): sym
                    for sym in universe
                }
                for fut in as_completed(fut_to_sym):
                    sym = fut_to_sym[fut]
                    data = fut.result()
                    if data:
                        feature_signals[sym] = self._extract_feature_values(data, config.features_required)

        correlation_signals: dict[str, dict[str, Any]] = {}
        if config.correlation_required:
            with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as pool:
                futures = {}
                for sym in universe:
                    fut = pool.submit(self._fetch_correlation_for_symbol, sym, config.correlation_required)
                    futures[fut] = sym
                for fut in as_completed(futures):
                    sym = futures[fut]
                    correlation_signals[sym] = fut.result()

        weights, pipeline_meta = self._pipeline.run(
            config=config,
            universe=universe,
            feature_signals=feature_signals,
            correlation_signals=correlation_signals,
            params={
                "max_weight": self._config.max_weight,
                "cash_floor": self._config.cash_floor,
            },
        )

        rule_trace = pipeline_meta.get("rule_trace", {})

        signal_values: dict[str, float] = {}
        for sym in universe:
            fs = feature_signals.get(sym, {})
            signal_values[sym] = fs.get("signal", 0.0)

        self._weight_storage.append_weights(
            strategy_name, weights, signal_values, run_id=actual_run_id,
            metadata={"symbols": universe[:5], "count": len(universe)},
        )
        self._meta_storage.log_run(strategy_name, actual_run_id, symbol=",".join(universe[:5]))

        result = StrategyResult(
            strategy_name=strategy_name,
            weights=self._weights_to_dataframe(weights, signal_values),
            run_id=actual_run_id,
            timestamp=datetime.utcnow(),
            metadata={"symbol_count": len(universe), "weights": weights},
            rule_trace=rule_trace,
        )
        return result

    def get_weights(
        self,
        strategy_name: str,
        symbol: str | None = None,
        from_ts: int | None = None,
        to_ts: int | None = None,
    ) -> list[dict[str, Any]]:
        df = self._weight_storage.read_weights(strategy_name, symbol, from_ts, to_ts)
        return df.to_dict(orient="records") if not df.empty else []

    def get_runs(self, strategy_name: str | None = None) -> list[dict[str, Any]]:
        return self._meta_storage.get_runs(strategy_name)

    def _resolve_universe(self, config: StrategyConfig, symbols: list[str] | None) -> list[str]:
        if symbols:
            return symbols
        source = config.universe.get("source", "watchlist")
        if source == "watchlist" and self._config.shared_watchlist_path:
            try:
                import json
                with open(self._config.shared_watchlist_path) as f:
                    return json.load(f)
            except Exception:
                LOG.warning("Could not load watchlist from %s", self._config.shared_watchlist_path)
        return config.universe.get("inline", ["AAPL", "MSFT", "GOOGL", "AMZN", "META"])

    def _fetch_correlation_for_symbol(self, sym: str, required: list[str]) -> dict[str, Any]:
        ctx: dict[str, Any] = {}
        if "impact" in required:
            ctx["impact"] = self._correlation_client.get_impact(sym)
        if "granger" in required or "correlation" in required:
            ctx["correlation"] = self._correlation_client.get_correlation(sym)
        if "drawdown" in required:
            ctx["drawdown"] = self._correlation_client.get_drawdown(sym)
        return self._flatten_correlation_context(ctx)

    def _extract_feature_values(self, data: dict[str, Any], indicators: list[str]) -> dict[str, float]:
        result: dict[str, float] = {}
        values = data.get("values", data)
        values_dict = {k.lower(): v for k, v in values.items()} if isinstance(values, dict) else {}
        for ind in indicators:
            raw = values_dict.get(ind.lower()) if isinstance(values, dict) else None
            try:
                result[ind] = float(raw) if raw is not None else 0.0
            except (TypeError, ValueError):
                result[ind] = 0.0
        sig = data.get("signal", data.get("signal_value", 0.0))
        try:
            result["signal"] = float(sig) if sig else 0.0
        except (TypeError, ValueError):
            result["signal"] = 0.0
        return result

    def _flatten_correlation_context(self, ctx: dict[str, Any]) -> dict[str, Any]:
        flat: dict[str, Any] = {}
        for key, value in ctx.items():
            if isinstance(value, dict):
                flat.update(value)
            else:
                flat[key] = value
        return flat

    def delete_weights(self, strategy_name: str, symbol: str | None = None) -> int:
        return self._weight_storage.delete_weights(strategy_name, symbol)

    def delete_runs(self, strategy_name: str | None = None) -> int:
        return self._meta_storage.delete_runs(strategy_name)

    def delete_run_by_id(self, run_id: str) -> bool:
        return self._meta_storage.delete_run_by_id(run_id)

    def _weights_to_dataframe(self, weights: dict[str, float], signal_values: dict[str, float]) -> "pd.DataFrame":
        import pandas as pd
        records = [
            {"symbol": sym, "weight": w, "signal_value": signal_values.get(sym, 0.0)}
            for sym, w in weights.items()
        ]
        return pd.DataFrame(records)
