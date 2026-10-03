from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any

from vinu_strategy.clients.features_client import FeaturesClient
from vinu_strategy.clients.correlation_client import CorrelationClient
from vinu_strategy.config import VinuStrategyConfig
from vinu_strategy.engine.pipeline import WeightPipeline
from vinu_strategy.engine.registry import StrategyRegistry
from vinu_strategy.models.strategy import StrategyConfig, StrategyResult
from vinu_strategy.storage.meta import MetaStorage
from vinu_strategy.storage.precondition_state import PreconditionStateStore
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
        self._precondition_state = PreconditionStateStore(config.data_root / "precondition_state.db")
        self._registry.load_all()
        self._sync_registry()

    def _sync_registry(self) -> None:
        for name, scfg in self._registry._strategies.items():
            self._meta_storage.register_strategy(name, scfg.description, scfg.schedule)

    def list_strategies(self) -> list[dict[str, Any]]:
        return self._meta_storage.get_registered_strategies()

    def get_strategy(self, name: str) -> StrategyConfig | None:
        return self._registry.get(name)

    def record_precondition_check(self, name: str, *, precondition_held: bool | None) -> None:
        """Point 6's write-back (see precondition_state.py's own module
        docstring for why this is a separate store, not the strategy's
        YAML file). Called for every real EXECUTE/SKIP `live_decision_agent`
        verdict -- callers decide which decisions count as a real check,
        this just records one."""
        self._precondition_state.record_check(
            name, precondition_held=precondition_held,
            checked_at=datetime.now(timezone.utc).isoformat(),
        )

    def get_precondition_state(self, name: str) -> dict[str, Any] | None:
        return self._precondition_state.get(name)

    def resolve_universe(self, name: str) -> list[str]:
        """Public wrapper on `_resolve_universe` -- needed by API consumers
        (e.g. vinu-live's live-decision poller, reverse-engineering/
        03-poller-and-state-schema.md) that need a strategy's ticker list
        without symbols already chosen, which `_resolve_universe` alone
        can't answer since it's private to `evaluate()`'s call site."""
        config = self._registry.get(name)
        if config is None:
            return []
        return self._resolve_universe(config, None)

    def evaluate(
        self,
        strategy_name: str,
        symbols: list[str] | None = None,
        run_id: str | None = None,
        dry_run: bool = False,
        as_of: int | None = None,
    ) -> StrategyResult:
        """`as_of` (item #22 finding #3, system-wide-audit-and-design/
        02-open-questions-strategy-and-simulation.md): "point-in-time
        safety is fully delegated upstream, with no verification at this
        layer" -- `FeaturesClient.get_features()` used to be called with
        no as_of at all, so its response always reflected whatever
        vinu-tools' feature route considered "now" at the exact moment
        each symbol's HTTP call happened to execute, not one consistent
        instant for the whole run. Captured ONCE here (defaulting to real
        wall-clock now when the caller doesn't pin one, e.g. for a
        backtest/replay run) and threaded through every `get_features`
        call below, so every symbol in one `evaluate()` call sees the
        same decision-time snapshot. Deliberately NOT threaded into
        `correlation_signals`/`angle_signals`: those are backed by
        `vinu-initial-analysis`'s `RunLog`-stored historical rows, each
        already pinned to its own `analysis_until` at write time -- a
        materially different point-in-time question (which stored run to
        read, not "is this live-fetched data corrupted by look-ahead")
        that this fix does not attempt to answer.
        """
        config = self._registry.get(strategy_name)
        if config is None:
            raise ValueError(f"Unknown strategy: {strategy_name}")
        effective_as_of = as_of if as_of is not None else int(datetime.now(timezone.utc).timestamp())

        if dry_run:
            import pandas as pd
            LOG.info("DRY RUN: evaluate(%s) — skipping execution", strategy_name)
            return StrategyResult(
                strategy_name=strategy_name,
                weights=pd.DataFrame(),
                run_id=run_id or f"{strategy_name}_dry_run",
                timestamp=datetime.utcnow(),
                metadata={"symbol_count": 0, "dry_run": True},
                rule_trace={},
            )

        actual_run_id = run_id or f"{strategy_name}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        universe = self._resolve_universe(config, symbols)
        if not universe:
            LOG.warning("Empty universe for strategy '%s'", strategy_name)

        feature_signals: dict[str, dict[str, float]] = {}
        if config.features_required:
            with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as pool:
                fut_to_sym = {
                    pool.submit(
                        self._features_client.get_features, sym,
                        indicators=config.features_required, as_of=effective_as_of,
                    ): sym
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

        angle_signals: dict[str, dict[str, Any]] = {}
        if config.angles_required:
            with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as pool:
                futures = {}
                for sym in universe:
                    fut = pool.submit(self._fetch_angles_for_symbol, sym, config.angles_required)
                    futures[fut] = sym
                for fut in as_completed(futures):
                    sym = futures[fut]
                    angle_signals[sym] = fut.result()

        weights, pipeline_meta = self._pipeline.run(
            config=config,
            universe=universe,
            feature_signals=feature_signals,
            correlation_signals=correlation_signals,
            angle_signals=angle_signals,
            params={
                "max_weight": self._config.max_weight,
                "cash_floor": self._config.cash_floor,
            },
        )

        rule_trace = pipeline_meta.get("rule_trace", {})
        sanity_issues = pipeline_meta.get("sanity_issues", {})
        data_quality = self._compute_data_quality(
            universe, config, feature_signals, correlation_signals, angle_signals,
        )

        signal_values: dict[str, float] = {}
        for sym in universe:
            fs = feature_signals.get(sym, {})
            signal_values[sym] = fs.get("signal", 0.0)

        self._weight_storage.append_weights(
            strategy_name, weights, signal_values, run_id=actual_run_id,
            metadata={"symbols": universe[:5], "count": len(universe)},
        )
        # v1 C4 (the-inconsistencies-v2 plan 2.4d): a degraded run (symbols missing required
        # upstream data, or weights clamped/zeroed by the sanity gate) used to be visible only
        # in this call's own response and one log line, then gone. Persist the facts on the run
        # row so GET /strategy/runs can answer "was this run clean" after the fact.
        self._meta_storage.log_run(
            strategy_name, actual_run_id, symbol=",".join(universe[:5]),
            metadata={
                "is_degraded": bool(data_quality),
                "degraded_symbols": sorted(data_quality)[:20],
                "sanity_issue_count": len(sanity_issues),
            },
        )
        try:
            from vinu_infra.pipeline_edge_recorder import record_edge

            record_edge(
                "strategy.run_quality->strategy.runs_api", "received",
                f"{strategy_name}: degraded={bool(data_quality)}, sanity_issues={len(sanity_issues)}",
            )
        except Exception:  # noqa: BLE001 -- observe-only
            pass

        if data_quality:
            LOG.warning(
                "[%s] Degraded run for '%s': %d/%d symbols missing required upstream "
                "data (real failure or a genuinely empty response -- either way, not "
                "counted as a clean 0.0 signal): %s",
                actual_run_id, strategy_name, len(data_quality), len(universe),
                {sym: dq["missing_sources"] for sym, dq in data_quality.items()},
            )
        # Not re-logged here -- WeightPipeline.run() already logs
        # sanity_issues with the same detail (engine/pipeline.py); the
        # real gap this closes is that nothing read it back out of
        # pipeline_meta into anything a caller could see, not that it
        # went unlogged.

        result = StrategyResult(
            strategy_name=strategy_name,
            weights=self._weights_to_dataframe(weights, signal_values),
            run_id=actual_run_id,
            timestamp=datetime.utcnow(),
            metadata={"symbol_count": len(universe), "weights": weights, "as_of": effective_as_of},
            rule_trace=rule_trace,
            data_quality=data_quality,
            sanity_issues=sanity_issues,
        )
        return result

    @staticmethod
    def _compute_data_quality(
        universe: list[str],
        config: StrategyConfig,
        feature_signals: dict[str, dict[str, float]],
        correlation_signals: dict[str, dict[str, Any]],
        angle_signals: dict[str, dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        """item #22 finding #1's concrete field, built exactly as
        specified: `{symbol: {missing_sources: [...], is_degraded: bool}}`.
        A source only counts as "missing" for a symbol if the strategy
        actually required it (`config.*_required`) -- a source that was
        never asked for was never expected to be there. Sparse: a symbol
        with everything it needed simply doesn't appear."""
        data_quality: dict[str, dict[str, Any]] = {}
        for sym in universe:
            missing: list[str] = []
            if config.features_required and not feature_signals.get(sym):
                missing.append("features")
            if config.correlation_required and not correlation_signals.get(sym):
                missing.append("correlation")
            if config.angles_required and not angle_signals.get(sym):
                missing.append("angles")
            if missing:
                data_quality[sym] = {"missing_sources": missing, "is_degraded": True}
        return data_quality

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

    def _fetch_angles_for_symbol(self, sym: str, angles: list[str]) -> dict[str, Any]:
        ctx: dict[str, Any] = {}
        for angle_name in angles:
            try:
                ctx[angle_name] = self._reduce_angle(angle_name, self._correlation_client.get_angle(sym, angle_name))
            except Exception:
                LOG.warning("Failed to fetch angle %s for %s", angle_name, sym)
        return ctx

    def _reduce_angle(self, angle_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        if angle_name != "regime_analysis":
            return payload
        rows = (payload or {}).get("data") or []
        # "current_regime" is the symbol's regime as of the most recent bar
        # -- what strategy filters actually need. This used to fall back to
        # scanning "regime_stats" rows for the highest pct_of_time, which
        # answers "what regime has this symbol mostly been in historically",
        # a different (and wrong) question for a live filter to be gating
        # on. The pct_of_time fallback below only fires against older,
        # not-yet-reprocessed regime_analysis payloads that predate the
        # current_regime row.
        current: dict[str, Any] | None = None
        best: dict[str, Any] | None = None
        for row in rows:
            metric = row.get("metric")
            if metric == "current_regime":
                current = row
            elif metric == "regime_stats":
                if best is None or (row.get("pct_of_time") or 0) > (best.get("pct_of_time") or 0):
                    best = row
        chosen = current or best
        if chosen is None:
            return payload
        return {
            "regime": chosen.get("regime"),
            **payload,
        }

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
