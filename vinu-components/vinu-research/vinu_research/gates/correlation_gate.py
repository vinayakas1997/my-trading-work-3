from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from vinu_research.config import ResearchConfig
from vinu_research.models import Artifact
from vinu_research.tools import ResearchTools

LOG = logging.getLogger(__name__)


@dataclass
class CorrelationVerdict:
    eligible: bool
    avg_correlation: float = 0.0
    max_correlation: float = 0.0
    n_active: int = 0
    correlations: dict[str, float] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)


async def check_correlation_gate(
    candidate_code: str,
    candidate_symbol: str,
    from_date: str,
    to_date: str,
    active_strategies: list[Artifact],
    tools: ResearchTools,
    config: ResearchConfig,
    interval: str = "1d",
) -> CorrelationVerdict:
    """Check if candidate strategy's daily returns are too correlated with
    existing active strategies.

    Runs a quick backtest for the candidate and each active strategy over
    the same date range, fetches their daily equity returns, and computes
    pairwise Pearson correlations. Returns a verdict with the average and
    maximum correlation values.

    When no active strategies exist, or backtesting fails for all of them,
    the gate passes (eligible=True) — no active strategies to correlate with.
    """
    if not active_strategies:
        return CorrelationVerdict(eligible=True, reasons=["no active strategies to compare against"])

    threshold = config.promotion_correlation_threshold

    # 1. Backtest candidate to get equity returns
    candidate_returns = await _backtest_and_get_returns(
        tools, candidate_code, candidate_symbol,
        from_date, to_date, interval,
    )
    if candidate_returns is None or len(candidate_returns) < 10:
        LOG.warning("Correlation gate: candidate has insufficient return data (%s points)", len(candidate_returns) if candidate_returns is not None else 0)
        return CorrelationVerdict(
            eligible=True,
            reasons=["candidate strategy has insufficient return data for correlation check"],
        )

    # 2. Backtest each active strategy and compute correlations
    correlations: dict[str, float] = {}
    for artifact in active_strategies:
        if not artifact.strategy_code:
            continue
        active_returns = await _backtest_and_get_returns(
            tools, artifact.strategy_code, candidate_symbol,
            from_date, to_date, interval,
        )
        if active_returns is None or len(active_returns) < 10:
            LOG.warning("Correlation gate: active strategy %s has insufficient return data", artifact.artifact_id)
            continue

        aligned = pd.concat(
            [candidate_returns, active_returns],
            axis=1, join="inner",
        )
        if len(aligned) < 10:
            continue
        corr = aligned.iloc[:, 0].corr(aligned.iloc[:, 1])
        correlations[artifact.artifact_id] = corr

    if not correlations:
        return CorrelationVerdict(
            eligible=True,
            reasons=["no active strategies had evaluable return data"],
        )

    n = len(correlations)
    avg_corr = sum(correlations.values()) / n
    max_corr = max(correlations.values())

    eligible = avg_corr < threshold
    reasons: list[str] = []
    if not eligible:
        reasons.append(
            f"average correlation {avg_corr:.3f} with {n} active "
            f"strategy(ies) exceeds threshold {threshold:.2f}"
        )
        if max_corr >= threshold:
            reasons.append(f"highest pairwise correlation {max_corr:.3f}")
    else:
        reasons.append(f"average correlation {avg_corr:.3f} within threshold {threshold:.2f}")

    return CorrelationVerdict(
        eligible=eligible,
        avg_correlation=avg_corr,
        max_correlation=max_corr,
        n_active=n,
        correlations=correlations,
        reasons=reasons,
    )


async def _backtest_and_get_returns(
    tools: ResearchTools,
    strategy_code: str,
    symbol: str,
    from_date: str,
    to_date: str,
    interval: str,
) -> pd.Series | None:
    """Run a quick backtest and fetch daily equity returns."""
    bt = await tools.run_backtest(
        strategy_code=strategy_code,
        strategy_class_name="UserStrategy",
        symbols=[symbol],
        from_date=from_date,
        to_date=to_date,
        indicators=["sma_20", "sma_50", "rsi_14"],
        interval=interval,
        run_validation=False,
    )
    if bt is None:
        return None
    returns = await tools.fetch_equity_returns(bt.run_id)
    return returns
