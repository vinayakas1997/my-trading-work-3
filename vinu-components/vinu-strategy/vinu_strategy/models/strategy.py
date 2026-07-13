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
    "correlation_required", "pipeline", "universe", "metadata",
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
    "risk": frozenset({"normalize", "none"}),
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
    pipeline: PipelineConfig = field(default_factory=PipelineConfig)
    universe: dict[str, Any] = field(default_factory=lambda: {"source": "watchlist"})
    metadata: dict[str, Any] = field(default_factory=dict)

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
            pipeline=PipelineConfig.from_dict(d.get("pipeline", {}), source),
            universe=d.get("universe", {"source": "watchlist"}),
            metadata=d.get("metadata", {}),
        )


@dataclass
class StrategyResult:
    strategy_name: str
    weights: pd.DataFrame
    run_id: str
    timestamp: datetime
    metadata: dict[str, Any] = field(default_factory=dict)
    rule_trace: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
