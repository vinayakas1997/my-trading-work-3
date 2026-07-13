from __future__ import annotations

import logging
from typing import Any

from vinu_strategy.engine.selection import run_selection
from vinu_strategy.engine.allocation import run_allocation
from vinu_strategy.engine.timing import run_timing
from vinu_strategy.engine.risk import run_risk
from vinu_strategy.models.strategy import StrategyConfig

LOG = logging.getLogger(__name__)


class WeightPipeline:
    def run(
        self,
        config: StrategyConfig,
        universe: list[str],
        feature_signals: dict[str, dict[str, float]] | None = None,
        correlation_signals: dict[str, dict[str, Any]] | None = None,
        params: dict[str, Any] | None = None,
    ) -> tuple[dict[str, float], dict[str, Any]]:
        pipeline = config.pipeline
        meta: dict[str, Any] = {}

        all_signal_values: dict[str, float] = {}
        signal_context: dict[str, dict[str, Any]] = {}
        if feature_signals:
            for sym, fields in feature_signals.items():
                all_signal_values[sym] = fields.get("signal", 0.0)
                signal_context.setdefault(sym, {})["features"] = fields
        if correlation_signals:
            for sym, fields in correlation_signals.items():
                signal_context.setdefault(sym, {})["correlation"] = fields

        candidates = run_selection(pipeline.selection.method, universe, all_signal_values, pipeline.selection.params, signal_context)
        meta["selection"] = {"method": pipeline.selection.method, "candidates": len(candidates), "universe_size": len(universe)}

        raw_weights = run_allocation(pipeline.allocation.method, candidates, all_signal_values, pipeline.allocation.params, signal_context)
        meta["allocation"] = {"method": pipeline.allocation.method, "symbols": len(raw_weights)}

        timed_weights, rule_trace = run_timing(pipeline.timing.method, raw_weights, signal_context, pipeline.timing.params)
        meta["timing"] = {"method": pipeline.timing.method, "rules_evaluated": bool(rule_trace)}

        risk_params = dict(pipeline.risk.params)
        if params:
            risk_params.setdefault("max_weight", params.get("max_weight"))
            risk_params.setdefault("cash_floor", params.get("cash_floor"))
        final_weights = run_risk(pipeline.risk.method, timed_weights, risk_params)
        meta["risk"] = {"method": pipeline.risk.method, "max_weight": risk_params.get("max_weight")}
        meta["rule_trace"] = rule_trace

        return final_weights, meta
