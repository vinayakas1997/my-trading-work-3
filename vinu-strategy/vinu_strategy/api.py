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
        }

    def evaluate(self, strategy_name: str, symbols: list[str] | None = None) -> dict[str, Any]:
        result = self._service.evaluate(strategy_name, symbols)
        resp: dict[str, Any] = {
            "strategy_name": result.strategy_name,
            "run_id": result.run_id,
            "timestamp": result.timestamp.isoformat(),
            "weights": result.weights.to_dict(orient="records"),
            "metadata": result.metadata,
        }
        if result.rule_trace:
            resp["rule_trace"] = result.rule_trace
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
