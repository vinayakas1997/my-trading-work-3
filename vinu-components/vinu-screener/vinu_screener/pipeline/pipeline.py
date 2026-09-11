"""Stage B (B10): the full daily_stock_analysis-shaped pipeline, wiring
B11-B14 (and B13's filter-chain shape) into one call: cached snapshot ->
hard filter -> factor score -> risk overlay -> concentration overlay ->
near-score rotation -> (optional) turnover gate -> top-N enrichment.

"Cached snapshot" is deliberately just this module's input, not something
it fetches itself -- Phase B-2's `ScanMonitor`/`SymbolDataSource` already
own fetching and caching (B4's `FeatureLibrary` cache, B9's timeout guard);
this pipeline is the *scoring/ranking* stage that runs on whatever survived
that, keeping with B15's decoupling principle: this module has no idea
where a snapshot came from, and nothing past `top_n_symbols` touches the
research/order pipeline -- it just returns a ranked list for something else
to act on.

"Top-N enrichment only" is the point of doing this in the shape DSA does:
an optional `enrich_fn` runs only against the final top-N, so a slow/
expensive detail fetch (deep fundamentals, an LLM pass, ...) is never paid
for the hundreds of symbols that get filtered or out-ranked first.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from .candidate import Candidate
from .concentration import ConcentrationConfig, apply_concentration_overlay
from .hard_filter import HardFilterConfig
from .risk_overlay import RiskOverlayConfig
from .rotation import RotationConfig, near_score_rotation
from .rule_filters import FilterChain, FilterContext, HardFilterRule, RiskVetoRule, StageCount
from .turnover import TurnoverConfig, TurnoverState, apply_turnover_gate

ScorerFn = Callable[[dict[str, float]], float]
EnrichFn = Callable[[str], Any]


@dataclass(frozen=True)
class PipelineConfig:
    top_n: int = 20
    hard_filter: HardFilterConfig = field(default_factory=HardFilterConfig)
    risk: RiskOverlayConfig = field(default_factory=RiskOverlayConfig)
    concentration: ConcentrationConfig = field(default_factory=ConcentrationConfig)
    rotation_band: float = 1.5
    rotation_enabled: bool = True
    turnover: TurnoverConfig | None = None   # None -- no turnover gate, rank is taken as-is


@dataclass
class PipelineResult:
    ranked: list[Candidate]          # every surviving candidate, best-first (post rotation)
    trace: list[StageCount]          # B13's per-stage before/after counts
    top: list[Candidate]             # ranked[:top_n] (or the turnover-gated held set, if configured)
    enrichment: dict[str, Any] = field(default_factory=dict)
    turnover_held: list[str] | None = None


class ScreenPipeline:
    def __init__(
        self,
        scorer: ScorerFn,
        cfg: PipelineConfig,
        *,
        turnover_state: TurnoverState | None = None,
    ) -> None:
        self._scorer = scorer
        self._cfg = cfg
        self._turnover_state = turnover_state or TurnoverState()

    def run(
        self,
        snapshots: dict[str, dict[str, float]],
        *,
        sectors: dict[str, str] | None = None,
        seed: int = 0,
        enrich_fn: EnrichFn | None = None,
    ) -> PipelineResult:
        sectors = sectors or {}
        candidates = [
            Candidate(symbol=symbol, fields=fields, sector=sectors.get(symbol))
            for symbol, fields in snapshots.items()
        ]

        chain = FilterChain([
            HardFilterRule(self._cfg.hard_filter),
            RiskVetoRule(self._cfg.risk),
        ])
        survivors, trace = chain.run(candidates, FilterContext())

        for c in survivors:
            try:
                c.factor_score = float(self._scorer(c.fields))
            except Exception:  # noqa: BLE001 -- a bad scorer input drops the candidate, doesn't abort the run
                c.factor_score = float("-inf")

        apply_concentration_overlay(survivors, self._cfg.concentration)

        ranked = sorted(survivors, key=lambda c: c.final_score, reverse=True)
        rotation_cfg = RotationConfig(top_n=self._cfg.top_n, band=self._cfg.rotation_band, enabled=self._cfg.rotation_enabled)
        ranked = near_score_rotation(ranked, rotation_cfg, seed=seed)

        turnover_held: list[str] | None = None
        if self._cfg.turnover is not None:
            symbol_order = [c.symbol for c in ranked]
            turnover_held = apply_turnover_gate(symbol_order, self._turnover_state, self._cfg.turnover)
            held_set = set(turnover_held)
            # Re-rank within the held set using the pipeline's own score order
            # (apply_turnover_gate only decides *membership*, not order).
            by_symbol = {c.symbol: c for c in ranked}
            top = [by_symbol[s] for s in ranked_symbols_in_order(ranked, held_set)]
        else:
            top = ranked[: self._cfg.top_n]

        enrichment: dict[str, Any] = {}
        if enrich_fn is not None:
            for c in top:
                try:
                    enrichment[c.symbol] = enrich_fn(c.symbol)
                except Exception:  # noqa: BLE001 -- enrichment failing must not drop the candidate from the shortlist
                    enrichment[c.symbol] = None

        return PipelineResult(ranked=ranked, trace=trace, top=top, enrichment=enrichment, turnover_held=turnover_held)


def ranked_symbols_in_order(ranked: list[Candidate], held_set: set[str]) -> list[str]:
    return [c.symbol for c in ranked if c.symbol in held_set]
