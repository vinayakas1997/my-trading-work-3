from __future__ import annotations

from typing import Any

from vinu_strategy.engine.rules_engine import RulesEngine as _RulesEngine


class RuleEngine:
    def __init__(self, rules_config: list[dict[str, Any]]) -> None:
        self._engine = _RulesEngine(rules_config)

    def evaluate(self, ctx: dict[str, Any]) -> dict[str, Any]:
        weights = ctx.get("weights", {})
        signal_ctx: dict[str, Any] = {
            "features": ctx.get("features", {}),
            "correlation": ctx.get("correlation", {}),
        }
        result_weights: dict[str, float] = {}
        all_traces: dict[str, list[dict[str, Any]]] = {}
        for sym, base in weights.items():
            adj, trace = self._engine.evaluate(float(base), signal_ctx)
            result_weights[sym] = adj
            if trace:
                all_traces[sym] = trace
        return {
            "weights": result_weights,
            "trace": all_traces,
            "cash": ctx.get("cash", 0.0),
        }
