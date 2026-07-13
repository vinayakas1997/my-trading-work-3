from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from vinu_research.llm_generator import _complexity_penalty
from vinu_research.models import BacktestResult, LlmCandidate
from vinu_research.walk_forward import deflated_sharpe_ratio


@dataclass
class RankedCandidate:
    candidate: LlmCandidate
    score: float
    risk_score: float = 0.0
    complexity_score: float = 0.0


def rank_candidates(
    candidates: list[LlmCandidate],
    backtest_results: list[BacktestResult | None] | None = None,
) -> list[RankedCandidate]:
    if backtest_results is None:
        backtest_results = [None] * len(candidates)

    # Every candidate here is one independent trial against the same data — ranking
    # by raw Sharpe rewards the candidate that got luckiest, not the one most likely
    # to be genuinely skillful. Correct for that with the deflated Sharpe ratio.
    n_trials = max(len(candidates), 1)

    ranked: list[RankedCandidate] = []
    for c, r in zip(candidates, backtest_results):
        score = 100.0
        score -= _complexity_penalty(c.code) * 100

        risk_score = 0.0
        if r is not None:
            m = r.metrics
            n_obs = max(r.equity_points - 1, 2)
            dsr = deflated_sharpe_ratio(
                sharpe=m.sharpe_ratio,
                n_trials=n_trials,
                n_obs=n_obs,
                skew=m.skewness,
                excess_kurtosis=m.kurtosis,
            )
            # Centered on 0.5 so an average-of-n_trials result gets no free bonus —
            # only candidates that clear the multiple-comparison bar are rewarded.
            score += (dsr - 0.5) * 60
            if m.max_drawdown < -0.3:
                score -= 20
            if m.win_rate > 0.5:
                score += 10
            score += min(m.total_return * 50, 25)
            risk_score = (max(0, m.sharpe_ratio) * 10) + (m.win_rate * 10) - abs(m.max_drawdown) * 30

        complexity_score = 100 - _complexity_penalty(c.code) * 100

        ranked.append(RankedCandidate(
            candidate=c,
            score=max(0, score),
            risk_score=risk_score,
            complexity_score=complexity_score,
        ))

    ranked.sort(key=lambda x: x.score, reverse=True)
    return ranked


def best_candidate(
    candidates: list[LlmCandidate],
    backtest_results: list[BacktestResult | None] | None = None,
) -> RankedCandidate | None:
    if not candidates:
        return None
    ranked = rank_candidates(candidates, backtest_results)
    return ranked[0]
