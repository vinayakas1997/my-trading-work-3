"""`RankerConfig`: the persisted shape of one "screen ranker" -- a
universe, a set of user-defined factor weights (B10's `ScorerFn`, made
declarative by `pipeline/scorer.py`), the pipeline knobs (top-N, hard
filter), and how often it should re-run. Mirrors `ScanRule`'s shape
deliberately -- same "config object + a store + a scheduler" pattern
already proven for condition rules, applied to ranking instead.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..pipeline.hard_filter import HardFilterConfig
from ..pipeline.scorer import FactorSpec

# Ranking a whole universe (fetch + N indicator computations per symbol,
# not just one condition check) is heavier per cycle than a single
# ScanRule's condition evaluation -- floored higher than ScanRule's 30s so
# a misconfigured ranker with a short interval can't repeatedly re-fetch
# and re-score a large universe faster than it can usefully change.
RANKER_MIN_INTERVAL_SEC = 300.0

# The natural default for "rank once at the start of the day" -- callers
# that want continuous re-ranking set a shorter interval_sec explicitly
# (still floored at RANKER_MIN_INTERVAL_SEC).
ONE_DAY_SEC = 86400.0


@dataclass(frozen=True)
class RankerConfig:
    ranker_id: str
    universe: tuple[str, ...]
    factors: tuple[FactorSpec, ...]
    top_n: int = 20
    hard_filter: HardFilterConfig = field(default_factory=HardFilterConfig)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "RankerConfig":
        return cls(
            ranker_id=raw["ranker_id"],
            universe=tuple(raw["universe"]),
            factors=tuple(FactorSpec.from_dict(f) for f in raw["factors"]),
            top_n=int(raw.get("top_n", 20)),
            hard_filter=HardFilterConfig(**raw.get("hard_filter", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        from dataclasses import asdict

        return {
            "ranker_id": self.ranker_id,
            "universe": list(self.universe),
            "factors": [f.to_dict() for f in self.factors],
            "top_n": self.top_n,
            "hard_filter": asdict(self.hard_filter),
        }
