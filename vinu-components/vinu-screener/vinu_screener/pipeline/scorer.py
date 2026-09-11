"""The "set the ranks" piece: a declarative factor-weight scorer so a
user can define what `ScreenPipeline`'s `factor_score` actually rewards
without writing Python. Each `FactorSpec` names one B4/B5 `FeatureLibrary`
indicator (with its own `params`/`field`/`offset`, same shape a condition
leaf already uses) and a `weight` -- positive rewards a higher value,
negative penalizes it. `make_weighted_scorer()` turns a tuple of these into
the plain `ScorerFn` `ScreenPipeline` already expects (`Callable[[dict[str,
float]], float]`), so nothing about the pipeline itself has to change to
support user-defined ranking -- this is purely a config-driven way to
build the one callable it was always designed to accept.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class FactorSpec:
    name: str                              # arbitrary label -- the key this factor's value is stored under
    indicator: str                         # a FeatureLibrary-registered indicator name (close/rsi/sma/...)
    weight: float
    params: dict[str, Any] = field(default_factory=dict)
    output_field: str = "value"            # which output column, for a multi-output indicator like macd
    offset: int = 0                        # bars back, same convention as a condition leaf's `offset`

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "FactorSpec":
        return cls(
            name=raw["name"],
            indicator=raw["indicator"],
            weight=float(raw["weight"]),
            params=dict(raw.get("params", {})),
            output_field=raw.get("output_field", raw.get("field", "value")),
            offset=int(raw.get("offset", 0)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name, "indicator": self.indicator, "weight": self.weight,
            "params": dict(self.params), "output_field": self.output_field, "offset": self.offset,
        }


def weighted_score(fields: dict[str, float], factors: tuple[FactorSpec, ...]) -> float:
    """Sum of `weight * value` over every factor whose value is present and
    finite in `fields` -- a missing or non-finite factor contributes 0
    rather than poisoning the whole score with a NaN (same fail-closed
    posture as B2's `all_finite`, applied to scoring instead of gating)."""
    total = 0.0
    for factor in factors:
        raw = fields.get(factor.name)
        try:
            value = float(raw)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue
        if not math.isfinite(value):
            continue
        total += factor.weight * value
    return total


def make_weighted_scorer(factors: tuple[FactorSpec, ...]):
    """Returns a `ScorerFn` closing over `factors` -- pass straight to
    `ScreenPipeline(scorer, cfg)` or (more commonly) let `RankerRunner`
    build one internally from a `RankerConfig`."""
    return lambda fields: weighted_score(fields, factors)
