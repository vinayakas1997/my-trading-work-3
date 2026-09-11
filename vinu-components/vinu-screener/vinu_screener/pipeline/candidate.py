"""The shared record type every Phase B-3 pipeline stage reads and writes.

One `Candidate` per symbol that survived the coarse filter (B7) and the
condition-tree scan (B1-B6, Phase B-1/B-2) -- everything downstream of that
(hard filter, factor score, risk overlay, concentration overlay, rotation,
turnover gate) mutates the same object rather than passing around parallel
dicts, so a dry-run trace (B19, Phase B-4) can eventually show one candidate's
full journey through every stage.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Candidate:
    symbol: str
    fields: dict[str, float]          # raw feature values the stages read (price, pe, rsi, volume_ratio, ...)
    sector: str | None = None
    factor_score: float = 0.0
    risk_penalty: float = 0.0
    risk_flags: list[str] = field(default_factory=list)
    concentration_penalty: float = 0.0
    vetoed: bool = False
    veto_reason: str = ""
    dropped_at: str = ""              # which stage removed it, "" if still alive -- diagnostic for B19 later

    @property
    def final_score(self) -> float:
        return self.factor_score - self.risk_penalty - self.concentration_penalty

    @property
    def alive(self) -> bool:
        return not self.vetoed and not self.dropped_at
