from __future__ import annotations

import logging
import math
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
        angle_signals: dict[str, dict[str, Any]] | None = None,
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
        if angle_signals:
            for sym, angles in angle_signals.items():
                signal_context.setdefault(sym, {})["angles"] = angles

        candidates = run_selection(pipeline.selection.method, universe, all_signal_values, pipeline.selection.params, signal_context)
        meta["selection"] = {"method": pipeline.selection.method, "candidates": len(candidates), "universe_size": len(universe)}

        raw_weights = run_allocation(pipeline.allocation.method, candidates, all_signal_values, pipeline.allocation.params, signal_context)
        meta["allocation"] = {"method": pipeline.allocation.method, "symbols": len(raw_weights)}

        timed_weights, rule_trace = run_timing(pipeline.timing.method, raw_weights, signal_context, pipeline.timing.params)
        meta["timing"] = {"method": pipeline.timing.method, "rules_evaluated": bool(rule_trace)}

        risk_params = dict(pipeline.risk.params)
        if params:
            if params.get("max_weight") is not None:
                risk_params.setdefault("max_weight", params.get("max_weight"))
            if params.get("cash_floor") is not None:
                risk_params.setdefault("cash_floor", params.get("cash_floor"))
        final_weights = run_risk(pipeline.risk.method, timed_weights, risk_params)
        meta["risk"] = {"method": pipeline.risk.method, "max_weight": risk_params.get("max_weight")}
        meta["rule_trace"] = rule_trace

        # item #22 finding #2 (system-wide-audit-and-design/
        # 02-open-questions-strategy-and-simulation.md): no stage
        # anywhere validated weights for NaN/inf or the allow_short
        # invariant, regardless of which risk method ran -- risk_none()
        # passes weights through completely unmodified, and
        # evaluate_expression() (engine/expression.py) returns `nan` on
        # division by zero rather than erroring, so a nan could flow
        # unchecked through allocation -> timing -> risk -> storage. One
        # final, method-agnostic gate here closes it for every risk
        # method at once, not one patch per method.
        final_weights, sanity_issues = self._sanitize_weights(
            final_weights, allow_short=risk_params.get("allow_short", True),
        )
        if sanity_issues:
            LOG.warning(
                "WeightPipeline sanity check dropped/clamped %d weight(s) for '%s': %s",
                len(sanity_issues), config.name, sanity_issues,
            )
        meta["sanity_issues"] = sanity_issues

        return final_weights, meta

    @staticmethod
    def _sanitize_weights(
        weights: dict[str, float], *, allow_short: bool,
    ) -> tuple[dict[str, float], dict[str, str]]:
        """Final, risk-method-agnostic validation gate. Non-finite
        weights are dropped outright -- a NaN/inf position size is never
        safe to act on, no matter how small. A negative weight when the
        strategy's own `allow_short=False` invariant is violated is
        clamped to 0.0 rather than dropped: it's usually a small
        numerical artifact surviving a risk method that didn't itself
        enforce the invariant (see `risk_none`'s own pass-through), not a
        real short signal, and clamping keeps the symbol visible in the
        result at its correct (zero) exposure instead of silently
        vanishing from the output entirely.
        """
        clean: dict[str, float] = {}
        issues: dict[str, str] = {}
        for sym, w in weights.items():
            if not math.isfinite(w):
                issues[sym] = f"non-finite weight {w!r} dropped"
                continue
            if not allow_short and w < 0:
                issues[sym] = f"negative weight {w!r} clamped to 0.0 (allow_short=False)"
                w = 0.0
            clean[sym] = w
        return clean, issues
