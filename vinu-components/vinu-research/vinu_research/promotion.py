"""BENCHING -> ACTIVE promotion bar.

There is no live/paper-trading shadow account in this codebase yet — no broker
account exists to run one against. Until that exists, the promotion gate is
built from what the research loop already computes for every run: the
deflated Sharpe ratio (multiple-comparisons-corrected confidence that
best_sharpe reflects real skill, cumulative across every past trial run
against the symbol — see ResearchService.run_research) and the true
out-of-sample holdout check (a trailing slice of data the refinement loop
never tuned against — see StrategyResearchLoop._split_research_and_holdout),
and the Probability of Backtest Overfitting (PBO, combinatorially symmetric
CV — see vinu_research.pbo) added in Stage 2 (how-to-make-it-live.md #19).
"""

from __future__ import annotations

from dataclasses import dataclass

from vinu_research.config import ResearchConfig
from vinu_research.gates.correlation_gate import CorrelationVerdict
from vinu_research.models import Artifact


@dataclass
class PromotionVerdict:
    eligible: bool
    reasons: list[str]


def _chosen_bar_row(artifact: Artifact) -> dict | None:
    """The per-bar-size measurement code stored for this artifact's bar size (bar_validation), or None for an artifact
    that was never measured per bar size."""
    import json

    if not getattr(artifact, "bar_evidence", "") or not getattr(artifact, "bar_interval", ""):
        return None
    try:
        evidence = json.loads(artifact.bar_evidence)
    except ValueError:
        return None
    if not isinstance(evidence, dict) or evidence.get("verified") is not True:
        return None
    for row in evidence.get("bars") or []:
        if isinstance(row, dict) and row.get("interval") == artifact.bar_interval:
            return row
    return None


def meets_promotion_bar(artifact: Artifact, config: ResearchConfig, correlation_verdict: CorrelationVerdict | None = None) -> PromotionVerdict:
    reasons: list[str] = []
    row = _chosen_bar_row(artifact)
    # PBO needs a set of parameter trials; a fixed rule has none and its measurement says so (`pbo_waived`). That waiver
    # holds only with a stored, verified per-bar measurement, and the stored trade count is re-checked here.
    pbo_waived = bool(row and row.get("pbo_waived") and artifact.pbo is None)
    if row is not None and int(row.get("trade_count") or 0) < config.min_trades_for_pass:
        reasons.append(f"only {int(row.get('trade_count') or 0)} trades on {artifact.bar_interval} bars; "
                       f"at least {config.min_trades_for_pass} are needed")

    if artifact.deflated_sharpe < config.promotion_deflated_sharpe_threshold:
        reasons.append(
            f"deflated_sharpe {artifact.deflated_sharpe:.3f} below threshold "
            f"{config.promotion_deflated_sharpe_threshold:.3f} — best_sharpe "
            f"{artifact.initial_sharpe:.3f} is not distinguishable from the best "
            f"of many trials at this confidence level"
        )

    if config.promotion_holdout_required:
        if artifact.holdout_passed is None:
            reasons.append(
                "holdout check required but was never computed for this artifact "
                "(date range was likely too short to carve a holdout)"
            )
        elif artifact.holdout_passed is False:
            reasons.append("failed the out-of-sample holdout check")

    if config.promotion_stress_test_required:
        if artifact.stress_test_passed is None:
            reasons.append(
                "stress test required but was never computed for this artifact "
                "(no configured crisis window had usable price data)"
            )
        elif artifact.stress_test_passed is False:
            reasons.append("failed at least one historical stress window")

    if config.promotion_pbo_required and not pbo_waived:
        if artifact.pbo is None:
            reasons.append(
                "PBO required but was never computed for this artifact "
                "(too few splits in the research window to run combinatorial CV)"
            )
        elif artifact.pbo > config.promotion_pbo_threshold:
            reasons.append(
                f"PBO {artifact.pbo:.3f} above severe-overfitting threshold "
                f"{config.promotion_pbo_threshold:.3f} — the observed edge across "
                f"trial parameter sets is more likely explained by selection bias "
                f"than genuine skill"
            )

    if correlation_verdict is not None and not correlation_verdict.eligible:
        reasons.extend(correlation_verdict.reasons)

    return PromotionVerdict(eligible=not reasons, reasons=reasons)
