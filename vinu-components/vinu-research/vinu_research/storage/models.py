from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

STATUS_PENDING = "pending"
STATUS_RUNNING = "running"
STATUS_DONE = "done"
STATUS_FAILED = "failed"
STATUS_DELETED = "deleted"
STATUS_APPROVED = "approved"


@dataclass
class ResearchRunRecord:
    user_idea: str
    symbol: str
    from_date: str
    to_date: str
    id: int | None = None
    status: str = STATUS_PENDING
    total_iterations: int = 0
    best_iteration: int = -1
    best_sharpe: float = 0.0
    best_max_dd: float = 0.0
    report_md: str = ""
    error_message: str | None = None
    approved: bool = False
    approved_at: str = ""
    created_at: str = ""
    updated_at: str = ""
    # The winning candidate's executable code, captured so approving a run can
    # persist a strategy artifact without re-running the research loop.
    strategy_code: str = ""
    # Deflated Sharpe ratio (probability the best_sharpe reflects genuine skill,
    # not the luckiest of many trials) — n_trials for this is cumulative across
    # every past research run for the symbol, not just this run's iterations.
    deflated_sharpe: float = 0.0
    # None when the date range was too short to carve a holdout at all.
    holdout_passed: bool | None = None
    # None when no stress window had usable price data.
    stress_test_passed: bool | None = None
    # Probability of Backtest Overfitting (Bailey/Borwein/Lopez de Prado
    # combinatorially symmetric CV, see vinu_research.pbo) for the winning
    # candidate — how much of the observed edge across all trial parameter
    # sets is explainable by selection bias alone. None when the run had too
    # few splits to compute it (see pbo.py's own PBO_MIN_SPLIT_PERIODS gate).
    # Stage 2 (how-to-make-it-live.md #19): this used to be computed and
    # returned in the live ResearchResult response but never persisted here
    # -- the warning vanished the moment the response was read, so it could
    # never be checked again at promotion time. Now persisted alongside
    # holdout_passed/stress_test_passed, the two other fields promotion.py
    # already gates on.
    pbo: float | None = None
    # Short, plain-English narrative of what happened and why — distinct
    # from report_md (a metrics-table markdown report). Best-effort LLM
    # call; empty if the LLM wasn't configured or the call failed. See
    # end-to-end-test's gap writeup: this is what makes a run's outcome
    # readable by a human/agent without them parsing report_md themselves.
    summary_text: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "user_idea": self.user_idea,
            "symbol": self.symbol,
            "from_date": self.from_date,
            "to_date": self.to_date,
            "status": self.status,
            "total_iterations": self.total_iterations,
            "best_iteration": self.best_iteration,
            "best_sharpe": self.best_sharpe,
            "best_max_dd": self.best_max_dd,
            "report_md": self.report_md,
            "error_message": self.error_message,
            "approved": self.approved,
            "approved_at": self.approved_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "strategy_code": self.strategy_code,
            "deflated_sharpe": self.deflated_sharpe,
            "holdout_passed": self.holdout_passed,
            "stress_test_passed": self.stress_test_passed,
            "summary_text": self.summary_text,
            "pbo": self.pbo,
        }
