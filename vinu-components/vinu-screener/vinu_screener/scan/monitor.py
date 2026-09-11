"""Stage B (B6): `ScanMonitor` — poll-mode scan execution, the two-tier
choice this stage settles on as the default (and, for now, the *only*
mode) for an ~8000-symbol universe.

FinceptTerminal runs two parallel modes sharing one condition evaluator:
`ScanMonitor` (poll — timer-driven, re-fetch + re-evaluate every symbol on
a fixed interval) and `RealtimeScanRunner` (a live quote-feed subscription
with a coalesced sweep). Only poll mode is built here, deliberately: the
adoption tracker's own reasoning (repeated in `03-stage-b-vinu-screener.md`)
is that a realtime-subscription mode doesn't scale to 8000 symbols and
isn't the right thing to build first. If a future need for near-real-time
reaction on a *small* watchlist shows up, `RealtimeScanRunner`'s coalesced-
sweep pattern is the reference to come back to — nothing here forecloses
that, it's simply out of scope until something concrete needs it (same
"revisit trigger" discipline as Stage C).

One `run_cycle()` call is: B7 coarse-filter the universe -> for each
survivor, B9-timeout-guarded OHLCV fetch -> B3 warm-up check -> B1/B2/B4/B5
evaluate the rule tree -> B8 edge+cooldown gate -> collect fires. The
interval between cycles is floored at a rate-limit-safe minimum, same
reasoning FinceptTerminal's own `interval_sec` floor (30s) documents.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from ..conditions.evaluator import evaluate
from ..conditions.lookback import required_bars
from ..conditions.schema import ConditionNode, parse_condition
from ..features.library import FeatureLibrary
from ..rules.actions import ActionsConfig
from .cooldown import CooldownGate
from .data_source import SymbolDataSource
from .timeout_guard import call_with_timeout
from .universe import CoarseFilter, coarse_select

LOG = logging.getLogger(__name__)

# FinceptTerminal floors ScanMonitor's poll interval at 30s as a rate-limit
# safety margin -- ported as this package's own floor for the same reason:
# an operator-set interval below this is silently raised, never honoured,
# so a misconfigured rule can't accidentally hammer the upstream at 8000
# symbols x however-many-seconds-too-fast.
MIN_INTERVAL_SEC = 30.0
DEFAULT_FETCH_TIMEOUT_SEC = 5.0


#: Stage B (B18): a `persistent` rule keeps scanning cycle after cycle,
#: re-firing whenever cooldown allows (the default, and the only mode
#: Phase B-2 knew about). A `one_shot` rule is meant to surface a
#: candidate once and then deactivate -- `ScanMonitor` never deactivates
#: anything itself (rule storage/lifecycle is outside this package's scope,
#: same B15 decoupling as everywhere else), it only *signals* the intent
#: via `CycleResult.deactivate_rule` for whatever owns the rule's active
#: flag to act on.
RULE_MODES = ("persistent", "one_shot")


@dataclass(frozen=True)
class ScanRule:
    rule_id: str
    condition: ConditionNode
    universe: tuple[str, ...]
    cooldown_min: float = 0.0
    coarse_filter: CoarseFilter = field(default_factory=CoarseFilter)
    actions: ActionsConfig = field(default_factory=ActionsConfig)   # B16
    mode: str = "persistent"                                        # B18

    def __post_init__(self) -> None:
        if self.mode not in RULE_MODES:
            raise ValueError(f"mode must be one of {RULE_MODES}, got {self.mode!r}")

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "ScanRule":
        return cls(
            rule_id=raw["rule_id"],
            condition=parse_condition(raw["condition"]),
            universe=tuple(raw["universe"]),
            cooldown_min=float(raw.get("cooldown_min", 0.0)),
            coarse_filter=CoarseFilter(**raw.get("coarse_filter", {})),
            actions=ActionsConfig.from_dict(raw.get("actions")),
            mode=raw.get("mode", "persistent"),
        )


@dataclass
class SymbolOutcome:
    symbol: str
    status: str   # "fired" | "no_match" | "insufficient_history" | "timeout" | "fetch_error" | "coarse_filtered"
    detail: str = ""


@dataclass
class CycleResult:
    rule_id: str
    started_at: float
    duration_sec: float
    fired: list[str]
    outcomes: list[SymbolOutcome]
    deactivate_rule: bool = False   # B18: True when a one_shot rule fired this cycle

    @property
    def evaluated_count(self) -> int:
        return sum(1 for o in self.outcomes if o.status in ("fired", "no_match"))


class ScanMonitor:
    def __init__(
        self,
        data_source: SymbolDataSource,
        *,
        library: FeatureLibrary | None = None,
        cooldown_gate: CooldownGate | None = None,
        fetch_timeout_sec: float = DEFAULT_FETCH_TIMEOUT_SEC,
        interval_sec: float = 60.0,
    ) -> None:
        self._data_source = data_source
        self._library = library or FeatureLibrary()
        self._cooldown = cooldown_gate or CooldownGate()
        self._fetch_timeout_sec = fetch_timeout_sec
        # Rate-limit floor -- see MIN_INTERVAL_SEC's docstring.
        self.interval_sec = max(interval_sec, MIN_INTERVAL_SEC)

    def run_cycle(self, rule: ScanRule, *, now: float | None = None) -> CycleResult:
        started = time.monotonic()
        now = now if now is not None else time.time()
        # B4: one cache per cycle, shared across every symbol/leaf this rule
        # touches -- cleared here, not per-symbol, so it can actually help.
        self._library.clear_cache()

        outcomes: list[SymbolOutcome] = []
        fired: list[str] = []
        min_bars = required_bars(rule.condition)

        universe = self._coarse_filtered(rule)
        skipped = set(rule.universe) - set(universe)
        outcomes.extend(SymbolOutcome(s, "coarse_filtered") for s in skipped)

        for symbol in universe:
            outcome = self._evaluate_symbol(rule, symbol, min_bars)
            outcomes.append(outcome)
            if outcome.status != "fired":
                continue
            if self._cooldown.should_fire(rule.rule_id, symbol, True, rule.cooldown_min, now=now):
                fired.append(symbol)
            else:
                outcome.status = "no_match"
                outcome.detail = "matched but suppressed by edge/cooldown gate"

        # Every symbol that matched-but-wasn't-armed-yet, or didn't match at
        # all, still has to tell the cooldown gate "condition was false this
        # cycle" so a future true reading is seen as a fresh edge.
        for outcome in outcomes:
            if outcome.status == "no_match" and "suppressed" not in outcome.detail:
                self._cooldown.should_fire(rule.rule_id, outcome.symbol, False, rule.cooldown_min, now=now)

        return CycleResult(
            rule_id=rule.rule_id, started_at=now,
            duration_sec=time.monotonic() - started,
            fired=fired, outcomes=outcomes,
            deactivate_rule=(rule.mode == "one_shot" and bool(fired)),
        )

    def _coarse_filtered(self, rule: ScanRule) -> list[str]:
        if rule.coarse_filter == CoarseFilter():
            return list(rule.universe)  # no-op filter -- skip the snapshot round-trip entirely
        snapshots: dict[str, dict[str, float]] = {}
        for symbol in rule.universe:
            snap = self._data_source.get_snapshot(symbol)
            if snap is not None:
                snapshots[symbol] = snap
        return coarse_select(snapshots, rule.coarse_filter)

    def _evaluate_symbol(self, rule: ScanRule, symbol: str, min_bars: int) -> SymbolOutcome:
        result = call_with_timeout(
            self._data_source.get_ohlcv, symbol, timeout_sec=self._fetch_timeout_sec,
        )
        if result.timed_out:
            LOG.warning("scan %s: fetch for %s timed out after %.1fs", rule.rule_id, symbol, self._fetch_timeout_sec)
            return SymbolOutcome(symbol, "timeout", result.error or "")
        if not result.ok:
            return SymbolOutcome(symbol, "fetch_error", result.error or "")
        ohlcv = result.value
        if ohlcv is None or len(ohlcv) < min_bars:
            got = 0 if ohlcv is None else len(ohlcv)
            return SymbolOutcome(symbol, "insufficient_history", f"have {got} bars, need {min_bars}")

        try:
            is_true = evaluate(rule.condition, ohlcv, self._library, symbol)
        except Exception as exc:  # noqa: BLE001 -- one bad symbol must not abort the cycle
            LOG.exception("scan %s: evaluation errored for %s", rule.rule_id, symbol)
            return SymbolOutcome(symbol, "fetch_error", str(exc))
        return SymbolOutcome(symbol, "fired" if is_true else "no_match")
