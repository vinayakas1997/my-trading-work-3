from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from vinu_strategy.config import VinuStrategyConfig, load_config
from vinu_strategy.service import StrategyService


class StrategyAPI:
    def __init__(self, config: VinuStrategyConfig | None = None):
        self._config = config or load_config()
        self._service = StrategyService(self._config)

    def list_strategies(self) -> list[dict[str, Any]]:
        return self._service.list_strategies()

    def get_strategy(self, name: str) -> dict[str, Any] | None:
        cfg = self._service.get_strategy(name)
        if cfg is None:
            return None
        return {
            "name": cfg.name,
            "description": cfg.description,
            "schedule": cfg.schedule,
            "features_required": cfg.features_required,
            "correlation_required": cfg.correlation_required,
            "pipeline": {
                "selection": cfg.pipeline.selection.method,
                "allocation": cfg.pipeline.allocation.method,
                "timing": cfg.pipeline.timing.method,
                "risk": cfg.pipeline.risk.method,
            },
            # Resolved (not raw config) universe -- needed by external
            # pollers (vinu-live's live-decision loop) that don't have
            # their own watchlist-loading logic and shouldn't grow one,
            # per the "reduce, don't rebuild" reasoning already applied
            # elsewhere in this design series.
            "universe": self._service.resolve_universe(name),
            "must_conditions": cfg.must_conditions,
            "confirmation_conditions": cfg.confirmation_conditions,
            "grace_window_bars": cfg.grace_window_bars,
            "live_decision_position_size": cfg.live_decision_position_size,
            # Point 6's write-back (reverse-engineering/
            # 05-deciding-agent-and-precondition-tracking.md Part C):
            # `tested`/`precondition_held`/`last_checked_at` are overlaid
            # from PreconditionStateStore, a separate store from this
            # strategy's own YAML file -- see that store's own module
            # docstring for why. No real check recorded yet still means
            # `tested: False`, same default the YAML-only version always
            # returned.
            "precondition": self._precondition_dict(name, cfg.precondition),
        }

    def _precondition_dict(self, name: str, base: dict[str, Any]) -> dict[str, Any]:
        precondition = {**base, "tested": False, "precondition_held": None, "last_checked_at": None}
        state = self._service.get_precondition_state(name)
        if state is not None:
            precondition.update(state)
        return precondition

    def record_precondition_check(self, name: str, *, precondition_held: bool | None) -> dict[str, Any]:
        cfg = self._service.get_strategy(name)
        if cfg is None:
            raise HTTPException(status_code=404, detail=f"Strategy '{name}' not found")
        self._service.record_precondition_check(name, precondition_held=precondition_held)
        return {"status": "ok", "name": name, "precondition": self._precondition_dict(name, cfg.precondition)}

    def evaluate(
        self, strategy_name: str, symbols: list[str] | None = None, as_of: int | None = None,
    ) -> dict[str, Any]:
        result = self._service.evaluate(strategy_name, symbols, as_of=as_of)
        resp: dict[str, Any] = {
            "strategy_name": result.strategy_name,
            "run_id": result.run_id,
            "timestamp": result.timestamp.isoformat(),
            "weights": result.weights.to_dict(orient="records"),
            "metadata": result.metadata,
        }
        if result.rule_trace:
            resp["rule_trace"] = result.rule_trace
        if result.data_quality:
            resp["data_quality"] = result.data_quality
        if result.sanity_issues:
            resp["sanity_issues"] = result.sanity_issues
        return resp

    def get_weights(
        self,
        strategy_name: str,
        symbol: str | None = None,
        from_ts: int | None = None,
        to_ts: int | None = None,
    ) -> list[dict[str, Any]]:
        return self._service.get_weights(strategy_name, symbol, from_ts, to_ts)

    def get_runs(self, strategy_name: str | None = None) -> list[dict[str, Any]]:
        return self._service.get_runs(strategy_name)

    def delete_weights(self, strategy_name: str, symbol: str | None = None) -> dict[str, Any]:
        deleted = self._service.delete_weights(strategy_name, symbol)
        return {"deleted": deleted, "strategy": strategy_name, "symbol": symbol}

    def delete_runs(self, strategy_name: str | None = None) -> dict[str, Any]:
        deleted = self._service.delete_runs(strategy_name)
        return {"deleted": deleted, "strategy": strategy_name}

    def delete_run_by_id(self, run_id: str) -> dict[str, Any]:
        found = self._service.delete_run_by_id(run_id)
        if not found:
            raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
        return {"deleted": True, "run_id": run_id}
