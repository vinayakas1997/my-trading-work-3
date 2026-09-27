from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

LOG = logging.getLogger(__name__)

_KNOWN_TOP_LEVEL_KEYS = frozenset({
    "name", "description", "schedule", "features_required",
    "correlation_required", "angles_required", "pipeline", "universe", "metadata",
    # Live-decision-loop fields (missing-pieces-of-system/new-theory-of-
    # trading/system-wide-audit-and-design/reverse-engineering/
    # 03-poller-and-state-schema.md Part B) -- must_conditions is item #1's
    # original hard-AND trigger list; confirmation_conditions is the
    # grace-window "soft condition" idea from 00-explanation.md; an empty
    # confirmation_conditions list means a fired must-condition goes
    # straight to ready_to_execute with no grace window.
    "must_conditions", "confirmation_conditions", "grace_window_bars", "precondition",
    # Point 7 option 1 (reverse-engineering/06-execution-handoff-and-
    # architecture.md): the target_weight a live EXECUTE decision on this
    # strategy's must_conditions produces. See the field's own docstring
    # below for why this can't default to anything but 0.0 (unsized/no-op).
    "live_decision_position_size",
})
_KNOWN_PIPELINE_KEYS = frozenset({"selection", "allocation", "timing", "risk"})
_KNOWN_STAGE_KEYS: dict[str, frozenset] = {
    "selection": frozenset({"method", "on", "min", "n"}),
    "allocation": frozenset({"method", "signal"}),
    "timing": frozenset({"method", "rules"}),
    "risk": frozenset({"method", "max_weight", "max_short_weight", "cash_floor", "allow_short"}),
}
_KNOWN_METHODS: dict[str, frozenset] = {
    "selection": frozenset({"all", "threshold", "top_n"}),
    "allocation": frozenset({"equal", "signal_scaled"}),
    "timing": frozenset({"none", "rules"}),
    # item #22 finding #5: "shock_aware" is a real, working method in
    # engine/risk.py's own RISK_METHODS dict -- missing here meant any
    # strategy using it logged a false "unknown risk method" warning at
    # load time despite working correctly at runtime.
    "risk": frozenset({"normalize", "none", "shock_aware"}),
}


def _warn_unknown(keys: set[str], known: frozenset, label: str, source: str = "") -> None:
    unknown = keys - known
    if unknown:
        prefix = f"[{source}] " if source else ""
        LOG.warning("%sUnknown keys in %s: %s", prefix, label, sorted(unknown))


def _warn_unknown_method(method: str, known: frozenset, stage: str, source: str = "") -> None:
    if method not in known:
        prefix = f"[{source}] " if source else ""
        LOG.warning("%sUnknown %s method '%s', will use fallback", prefix, stage, method)


@dataclass
class PipelineStage:
    method: str
    params: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict, stage_name: str = "", source: str = "") -> PipelineStage:
        known_keys = _KNOWN_STAGE_KEYS.get(stage_name, frozenset())
        _warn_unknown(set(d.keys()), known_keys, f"pipeline.{stage_name}", source)
        method = d.get("method", "none")
        known_methods = _KNOWN_METHODS.get(stage_name, frozenset())
        _warn_unknown_method(method, known_methods, stage_name, source)
        return cls(method=method, params={k: v for k, v in d.items() if k != "method"})


@dataclass
class PipelineConfig:
    selection: PipelineStage = field(default_factory=lambda: PipelineStage("all"))
    allocation: PipelineStage = field(default_factory=lambda: PipelineStage("equal"))
    timing: PipelineStage = field(default_factory=lambda: PipelineStage("none"))
    risk: PipelineStage = field(default_factory=lambda: PipelineStage("normalize"))

    @classmethod
    def from_dict(cls, d: dict, source: str = "") -> PipelineConfig:
        _warn_unknown(set(d.keys()), _KNOWN_PIPELINE_KEYS, "pipeline", source)
        return cls(
            selection=PipelineStage.from_dict(d.get("selection", {}), "selection", source),
            allocation=PipelineStage.from_dict(d.get("allocation", {}), "allocation", source),
            timing=PipelineStage.from_dict(d.get("timing", {}), "timing", source),
            risk=PipelineStage.from_dict(d.get("risk", {}), "risk", source),
        )


@dataclass
class StrategyConfig:
    """Loaded from a YAML strategy definition file."""
    name: str
    description: str
    schedule: str
    features_required: list[str] = field(default_factory=list)
    correlation_required: list[str] = field(default_factory=list)
    angles_required: list[str] = field(default_factory=list)
    pipeline: PipelineConfig = field(default_factory=PipelineConfig)
    universe: dict[str, Any] = field(default_factory=lambda: {"source": "watchlist"})
    metadata: dict[str, Any] = field(default_factory=dict)
    # Hard-AND trigger conditions (item #1's original must-condition schema,
    # e.g. {"source": "live_indicators", "key": "sma_5_cross_sma_50", ...}) --
    # a fired must-condition either has all of these true, or there is no
    # setup at all (00-explanation.md Layer 1: "no grace period applies
    # here -- a cross either happened or it didn't").
    must_conditions: list[dict[str, Any]] = field(default_factory=list)
    # Soft/near-miss conditions given a grace window to confirm before the
    # setup is abandoned (00-explanation.md's original grace-window idea).
    # Empty means no grace window -- a fired must-condition goes straight
    # to ready_to_execute.
    confirmation_conditions: list[dict[str, Any]] = field(default_factory=list)
    # Guessed starting constant, same posture as FORWARD_HORIZON_BARS/
    # floor_multiple elsewhere in this design series -- meant to be
    # revisited once Layer 4's evidence table (point 9, deliberately
    # deferred) exists to derive a real value from.
    grace_window_bars: int = 10
    # 03-strategy-definition-full-schema.md item 4's precondition claim
    # -- description + defined here (static, config-time facts); `tested`
    # deliberately NOT stored as config, since 05-deciding-agent-and-
    # precondition-tracking.md leaves the write-back path/storage for
    # "has this actually been checked against real evidence yet"
    # explicitly undecided -- flipping it here would mean silently
    # editing this strategy's own YAML definition file from a live
    # agent call, which is a real architectural decision that hasn't
    # been made, not a safe default to assume.
    precondition: dict[str, Any] = field(default_factory=lambda: {"description": "", "defined": False})
    # Point 7 option 1 (reverse-engineering/06-execution-handoff-and-
    # architecture.md, "as a new target_weights contributor"): the
    # target_weight LiveScheduler should use when this strategy's
    # must_conditions produce a real EXECUTE decision. Defaults to 0.0
    # ("not sized") rather than any guessed nonzero fraction -- a
    # must-condition-only strategy has no other sizing mechanism defined
    # anywhere (the normal selection/allocation/timing/risk pipeline is a
    # separate mechanism, not automatically shared with must_conditions),
    # so inventing a default here would be fabricating real position
    # sizing, not a safe fallback. A strategy author must set this
    # explicitly for an EXECUTE decision to actually produce an order --
    # until then, LiveScheduler logs it clearly and skips.
    live_decision_position_size: float = 0.0

    @classmethod
    def from_dict(cls, d: dict, source: str = "") -> StrategyConfig:
        _warn_unknown(set(d.keys()), _KNOWN_TOP_LEVEL_KEYS, "strategy", source)
        serialized_name = d.get("name", "?")
        if not source:
            source = serialized_name
        return cls(
            name=serialized_name,
            description=d.get("description", ""),
            schedule=d.get("schedule", "daily"),
            features_required=d.get("features_required", []),
            correlation_required=d.get("correlation_required", []),
            angles_required=d.get("angles_required", []),
            pipeline=PipelineConfig.from_dict(d.get("pipeline", {}), source),
            universe=d.get("universe", {"source": "watchlist"}),
            metadata=d.get("metadata", {}),
            must_conditions=d.get("must_conditions", []),
            confirmation_conditions=d.get("confirmation_conditions", []),
            grace_window_bars=int(d.get("grace_window_bars", 10)),
            precondition=d.get("precondition", {"description": "", "defined": False}),
            live_decision_position_size=float(d.get("live_decision_position_size", 0.0)),
        )


@dataclass
class StrategyResult:
    strategy_name: str
    weights: pd.DataFrame
    run_id: str
    timestamp: datetime
    metadata: dict[str, Any] = field(default_factory=dict)
    rule_trace: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    # item #22 finding #1 (system-wide-audit-and-design/
    # 02-open-questions-strategy-and-simulation.md): BaseClient._request
    # (clients/base.py) catches every upstream failure (timeout, connect
    # error, 4xx/5xx) and returns `{}` rather than raising -- service.py's
    # own feature/correlation/angle fetches then silently treat that `{}`
    # as "no data for this symbol," defaulting straight to 0.0/empty with
    # nothing anywhere flagging the run as degraded. A genuine
    # infrastructure outage used to produce output indistinguishable from
    # "this symbol legitimately has no signal." Sparse -- only symbols
    # missing at least one REQUIRED source appear here at all, matching
    # this file's own convention for optional per-symbol data elsewhere.
    data_quality: dict[str, dict[str, Any]] = field(default_factory=dict)
    # item #22 finding #2: WeightPipeline.run's own final sanity gate
    # (engine/pipeline.py::_sanitize_weights) computes this and puts it
    # in its own internal `meta` dict -- surfaced here so it actually
    # reaches a caller instead of being one more "computed, then
    # discarded before it leaves the function" gap (the same recurring
    # shape item #21.3 already names three other instances of).
    # {symbol: "why it was dropped/clamped"}, sparse -- empty on a
    # healthy run.
    sanity_issues: dict[str, str] = field(default_factory=dict)
