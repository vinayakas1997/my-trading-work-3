"""BENCHING -> ACTIVE promotion bar.

There is no live/paper-trading shadow account in this codebase yet — no broker
account exists to run one against. Until that exists, the promotion gate is
built from what the research loop already computes for every run: the
deflated Sharpe ratio (multiple-comparisons-corrected confidence that
best_sharpe reflects real skill, cumulative across every past trial run
against the symbol — see ResearchService.run_research) and the true
out-of-sample holdout check (a trailing slice of data the refinement loop
never tuned against — see StrategyResearchLoop._split_research_and_holdout).
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


def meets_promotion_bar(artifact: Artifact, config: ResearchConfig, correlation_verdict: CorrelationVerdict | None = None) -> PromotionVerdict:
    reasons: list[str] = []

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

    if correlation_verdict is not None and not correlation_verdict.eligible:
        reasons.extend(correlation_verdict.reasons)

    return PromotionVerdict(eligible=not reasons, reasons=reasons)
