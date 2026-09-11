"""Stage B (B13): the `IPairList` filter-chain pattern, ported from
Freqtrade's `freqtrade/plugins/pairlist/IPairList.py` +
`pairlistmanager.py`. Each filter stage in the pipeline (B11's hard filter,
B12's risk veto, a B1-B6 condition tree, ...) is wrapped as one small class
declaring its own name, a JSON-shaped param schema (for a future rule-builder
UI or validation layer), and a `supports_backtesting` marker -- Freqtrade's
own small-but-telling detail: a filter that reads state only meaningful
live (an LLM confidence score with no historical record, say) shouldn't be
silently allowed into a backtest and produce a falsely-clean result.

`FilterChain` runs an ordered list of these over a `list[Candidate]`,
recording a before/after count at each stage -- exactly the per-stage trace
B19's dry-run UX (Phase B-4) will want to render, built here as a natural
side effect of the chain shape rather than bolted on later.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, fields as dataclass_fields, is_dataclass
from enum import Enum
from typing import Any

import pandas as pd

from ..conditions.evaluator import evaluate
from ..conditions.schema import ConditionNode
from ..features.library import FeatureLibrary
from .candidate import Candidate
from .hard_filter import HardFilterConfig, hard_filter_reasons
from .risk_overlay import RiskOverlayConfig, apply_risk_overlay


class SupportsBacktesting(str, Enum):
    NO = "NO"        # inherently live-only, e.g. reads a feed with no historical record
    BIASED = "BIASED"  # runs in backtest but may leak lookahead/live-only info -- warn, don't refuse
    YES = "YES"       # safe: uses only point-in-time, reproducible-from-history inputs


@dataclass(frozen=True)
class FilterContext:
    """What a filter stage may need beyond the candidate list itself.
    `ohlcv`/`library` are only required by condition-tree-based filters
    (`ConditionRule`) -- field-only filters (`HardFilterRule`,
    `RiskVetoRule`) never touch them."""

    ohlcv: dict[str, pd.DataFrame] | None = None
    library: FeatureLibrary | None = None


def _param_schema_of(cfg: Any) -> dict[str, str]:
    if not is_dataclass(cfg):
        return {}
    return {f.name: f.type if isinstance(f.type, str) else getattr(f.type, "__name__", str(f.type))
            for f in dataclass_fields(cfg)}


class ScanFilter(ABC):
    name: str
    supports_backtesting: SupportsBacktesting = SupportsBacktesting.YES

    @abstractmethod
    def param_schema(self) -> dict[str, str]: ...

    @abstractmethod
    def apply(self, candidates: list[Candidate], context: FilterContext) -> list[Candidate]:
        """Return the surviving candidates. Never mutate a candidate's
        identity (symbol) -- score/penalty/veto fields on the objects
        passed through may be updated in place."""
        ...


class HardFilterRule(ScanFilter):
    """Wraps B11's `HardFilterConfig`. Point-in-time price/volume/valuation
    bands read from a candidate's already-computed `fields` -- reproducible
    identically in a backtest given the same historical fields, hence
    `YES`."""

    def __init__(self, cfg: HardFilterConfig, *, name: str = "hard_filter") -> None:
        self.name = name
        self.supports_backtesting = SupportsBacktesting.YES
        self._cfg = cfg

    def param_schema(self) -> dict[str, str]:
        return _param_schema_of(self._cfg)

    def apply(self, candidates: list[Candidate], context: FilterContext) -> list[Candidate]:
        survivors = []
        for c in candidates:
            reasons = hard_filter_reasons(c.fields, self._cfg)
            if reasons:
                c.dropped_at = self.name
            else:
                survivors.append(c)
        return survivors


class RiskVetoRule(ScanFilter):
    """Wraps B12's risk overlay, but only for its *veto* outcome -- the
    additive penalty itself is applied separately (`apply_risk_overlay` is
    called again, or its result cached, by the pipeline stage that scores
    survivors; this filter only removes hard vetoes from the candidate set).
    Marked `BIASED`: several of DSA's own risk signals (LLM confidence,
    LLM-declared risk, deep-analysis flags) have no guaranteed historical
    record to replay in a backtest unless that verdict was itself persisted
    at the time -- a backtest run without that persisted trail would silently
    see those checks as never-triggered, which is exactly the lookahead-bias
    class of problem Freqtrade's marker exists to flag."""

    def __init__(self, cfg: RiskOverlayConfig, *, name: str = "risk_veto") -> None:
        self.name = name
        self.supports_backtesting = SupportsBacktesting.BIASED
        self._cfg = cfg

    def param_schema(self) -> dict[str, str]:
        return {"max_penalty": "float", "veto_penalty_threshold": "float | None", "veto_high_risk": "bool"}

    def apply(self, candidates: list[Candidate], context: FilterContext) -> list[Candidate]:
        survivors = []
        for c in candidates:
            result = apply_risk_overlay(c.fields, self._cfg)
            c.risk_penalty = result.penalty
            c.risk_flags = result.flags
            if result.vetoed:
                c.vetoed = True
                c.veto_reason = result.veto_reason
                c.dropped_at = self.name
            else:
                survivors.append(c)
        return survivors


class ConditionRule(ScanFilter):
    """Wraps a B1-B6 condition tree as one filter-chain stage -- the same
    schema a `vinu-screener` rule's `condition` field already uses (Phase
    B-1/B-2), reused here rather than inventing a second condition
    language for the pipeline's own filter stage. `YES`: the evaluator
    (`conditions/evaluator.py`) only ever reads the current bar and one bar
    back, so replaying it bar-by-bar in a backtest produces the same
    decision a live poll would have made at that point in history."""

    def __init__(self, condition: ConditionNode, *, name: str = "condition") -> None:
        self.name = name
        self.supports_backtesting = SupportsBacktesting.YES
        self._condition = condition

    def param_schema(self) -> dict[str, str]:
        return {"condition": "ConditionNode"}

    def apply(self, candidates: list[Candidate], context: FilterContext) -> list[Candidate]:
        if context.ohlcv is None or context.library is None:
            raise ValueError(f"{self.name}: ConditionRule needs FilterContext.ohlcv and .library")
        survivors = []
        for c in candidates:
            ohlcv = context.ohlcv.get(c.symbol)
            if ohlcv is None:
                c.dropped_at = self.name
                continue
            try:
                is_true = evaluate(self._condition, ohlcv, context.library, c.symbol)
            except Exception:  # noqa: BLE001 -- one bad symbol must not abort the chain
                is_true = False
            if is_true:
                survivors.append(c)
            else:
                c.dropped_at = self.name
        return survivors


@dataclass
class StageCount:
    stage: str
    supports_backtesting: SupportsBacktesting
    before: int
    after: int


class FilterChain:
    def __init__(self, filters: list[ScanFilter]) -> None:
        self.filters = filters

    def run(self, candidates: list[Candidate], context: FilterContext) -> tuple[list[Candidate], list[StageCount]]:
        current = candidates
        trace: list[StageCount] = []
        for filt in self.filters:
            before = len(current)
            current = filt.apply(current, context)
            trace.append(StageCount(filt.name, filt.supports_backtesting, before, len(current)))
        return current, trace
