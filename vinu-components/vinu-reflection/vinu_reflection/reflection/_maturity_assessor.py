"""MaturityAssessor -- a deterministic (no LLM), read-only system-wide
maturity tier. Design reference: missing-pieces-of-system/maturity-
agentic-system/00-maturity-agentic-system-explanation.md.

Not a Finding-writing analyst itself (no `ANALYST_NAME`/`run()` matching
the `cli.py` `ANALYSTS` shape) -- a shared, importable computation, same
"library function, not a reasoning agent" posture the design doc itself
calls for. Analysis T (`lesson_maturity_baseline_check.py`) is its first
real consumer, built the same day this module was, once this existed to
compare against; the design doc's own later steps (wiring a live
`GET /maturity/status` into Planner/risk_gatekeeper/capital_allocator)
are explicitly a separate, later phase -- not attempted here.

**Real scope-down from the design doc's own source-store list,
documented**: the doc lists 5 source stores (`trade_score_calibration_
history.jsonl`, `calibration_entries`/`angle_calibration_entries`,
`paper_performance`, vinu-live's position book, `trade_audit_log.jsonl`).
This module reads only 2: `calibration_entries` (vinu-research) and
`paper_performance` (vinu-agent) -- both already mount-and-imported by
this service (`paper_live_correlation.py` established the exact same
pair). The other 3 aren't a new join: `calibration_entries` is *already*
populated only from closed *live* broker positions, via vinu-live's
`feedback_loop.record_realized_outcome()` reading `list_closed_positions()`
off the real position book (confirmed in `paper_live_correlation.py`'s
own docstring) -- re-reading the position book or `trade_audit_log.jsonl`
directly would re-derive the same real trade outcomes a second time, not
add new evidence. `trade_score_calibration_history.jsonl` is a
per-TradeScore-subscore diagnostic, not a trade-count/accuracy source
distinct from `calibration_entries` for this module's purposes. Revisit
if a real need for those specific files surfaces later.

**Tier thresholds, grounded not invented** (matching the design doc's own
"tier logic" list, its own text flagged "illustrative, not final"):
- `MIN_PAPER_DAYS = 5` -- reused as-is from `paper_live_correlation.py`
  (V), itself matching `ShadowEvaluator`'s own `min_paper_days` gating.
- `MATURE_MIN_TRADES = 30` -- reused as-is from
  `trade_score_calibration.py`'s own `compute_calibration_metrics()`
  default `min_sample` -- literally "the minimum sample size
  `trade_score_calibration.py` already requires before it lets
  calibration nudge thresholds," the exact bar the design doc's own
  `early_live`/`mature` boundary text names.
- `MATURE_MIN_REGIMES = 2` -- `Artifact.regime_tag`'s real value set
  (`models.py`: "09 step2: trend/range/high-vol") has exactly 3 members;
  requiring a majority of them (2 of 3) grounds "broad enough regime
  coverage" in the real taxonomy instead of an arbitrary number.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from vinu_research.models import Artifact, CalibrationEntry

from vinu_agent.broker.performance_store import PaperPerformanceStore
from vinu_agent.broker.research_link import get_strategy_store

MIN_PAPER_DAYS = 5
MATURE_MIN_TRADES = 30
MATURE_MIN_REGIMES = 2

TIER_COLD_START = "cold_start"
TIER_PAPER_ONLY = "paper_only"
TIER_EARLY_LIVE = "early_live"
TIER_MATURE = "mature"
TIER_ORDER = [TIER_COLD_START, TIER_PAPER_ONLY, TIER_EARLY_LIVE, TIER_MATURE]

# T's own comparison need (see `recent_form_reading()` below), not part of
# the core tier -- deliberately the same "last 5" shape as LESSON's own
# `last5` win/loss string, so the two sides are directly comparable.
MIN_RECENT_FORM_ENTRIES = 5


class MaturityAssessment:
    def __init__(
        self,
        *,
        tier: str,
        n_real_trades: int,
        n_paper_trading_days: int,
        directional_accuracy: float,
        brier_mean: float,
        live_trade_fraction: float,
        regime_coverage: list[str],
    ) -> None:
        self.tier = tier
        self.n_real_trades = n_real_trades
        self.n_paper_trading_days = n_paper_trading_days
        self.directional_accuracy = directional_accuracy
        self.brier_mean = brier_mean
        self.live_trade_fraction = live_trade_fraction
        self.regime_coverage = regime_coverage

    @property
    def tier_ordinal(self) -> int:
        return TIER_ORDER.index(self.tier)

    def as_dict(self) -> dict[str, Any]:
        return {
            "tier": self.tier,
            "n_real_trades": self.n_real_trades,
            "n_paper_trading_days": self.n_paper_trading_days,
            "directional_accuracy": self.directional_accuracy,
            "brier_mean": self.brier_mean,
            "live_trade_fraction": self.live_trade_fraction,
            "regime_coverage": self.regime_coverage,
        }


def _all_calibration_entries(strategy_store) -> list[tuple[CalibrationEntry, Artifact]]:
    """Every real calibration entry across every artifact, paired with its
    parent Artifact (for `regime_tag`) -- the one system-wide join both
    `assess()` and `recent_form_reading()` need."""
    pairs: list[tuple[CalibrationEntry, Artifact]] = []
    for artifact in strategy_store.list_artifacts():
        for entry in strategy_store.get_calibration_entries(artifact.artifact_id):
            pairs.append((entry, artifact))
    return pairs


def assess(data_root_paths: dict[str, Path]) -> MaturityAssessment:
    agent_root = Path(data_root_paths["vinu_agent"])
    performance_store = PaperPerformanceStore(agent_root / "paper_performance.db")
    strategy_store = get_strategy_store()

    all_paper = performance_store.get_all()
    n_paper_trading_days = sum(len(returns) for returns in all_paper.values())
    n_artifacts_with_paper_history = sum(
        1 for returns in all_paper.values() if len(returns) >= MIN_PAPER_DAYS
    )

    pairs = _all_calibration_entries(strategy_store)
    n_real_trades = len(pairs)
    n_promoted_artifacts = len({artifact.artifact_id for _, artifact in pairs})
    directional_correct_count = sum(1 for entry, _ in pairs if entry.directional_correct)
    brier_sum = sum(entry.brier_score for entry, _ in pairs)
    regime_coverage = sorted({artifact.regime_tag for _, artifact in pairs if artifact.regime_tag})

    directional_accuracy = directional_correct_count / n_real_trades if n_real_trades else 0.0
    brier_mean = brier_sum / n_real_trades if n_real_trades else 0.0
    live_trade_fraction = (
        n_promoted_artifacts / n_artifacts_with_paper_history
        if n_artifacts_with_paper_history
        else 0.0
    )

    if n_real_trades >= MATURE_MIN_TRADES and len(regime_coverage) >= MATURE_MIN_REGIMES:
        tier = TIER_MATURE
    elif n_real_trades > 0:
        tier = TIER_EARLY_LIVE
    elif n_artifacts_with_paper_history > 0:
        tier = TIER_PAPER_ONLY
    else:
        tier = TIER_COLD_START

    return MaturityAssessment(
        tier=tier,
        n_real_trades=n_real_trades,
        n_paper_trading_days=n_paper_trading_days,
        directional_accuracy=directional_accuracy,
        brier_mean=brier_mean,
        live_trade_fraction=live_trade_fraction,
        regime_coverage=regime_coverage,
    )


def recent_form_reading(data_root_paths: dict[str, Path]) -> str | None:
    """A crude 'recent form' read from the most recent
    `MIN_RECENT_FORM_ENTRIES` real calibration entries system-wide,
    ordered by their own `timestamp` -- not part of the core tier above,
    and not persisted anywhere; exists purely so analysis T has something
    directly comparable in shape to LESSON's own `last5` win/loss string.
    `None` below the evidence floor (fewer real entries than that exist
    at all), same "no reading, not a reading of zero" posture as
    `dl_angle_backtest_health.py`'s staleness check returning nothing
    below its own floor."""
    strategy_store = get_strategy_store()
    pairs = _all_calibration_entries(strategy_store)
    if len(pairs) < MIN_RECENT_FORM_ENTRIES:
        return None
    recent = sorted(pairs, key=lambda pair: pair[0].timestamp)[-MIN_RECENT_FORM_ENTRIES:]
    correct = sum(1 for entry, _ in recent if entry.directional_correct)
    incorrect = len(recent) - correct
    if correct > incorrect:
        return "improving"
    if incorrect > correct:
        return "degrading"
    return "flat"
