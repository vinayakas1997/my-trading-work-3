"""The trade journal for the live-decision loop: for each closed position, the whole story in one record -- why it
was opened (the entry decision and its reasoning), what the reviews said while it was held, how and why it closed,
what it returned, and the plain cause tag of a loss. Plus a track record of plain counts.

Everything here is read from rows the loop already wrote; nothing is computed that was not recorded. A return that
was never recorded stays `None` and is counted as unknown, never as a loss or a win. No win probability is invented:
the track record is raw counts and the mean of the recorded returns, the same honesty rule the agent's prompt states.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from vinu_live.live_decision.schema import LiveDecisionOpenPosition
from vinu_live.live_decision.storage import LiveDecisionBackend, list_closed_positions, list_live_decisions


def classify_live_exit(closed_reason: str, return_pct: float | None) -> str:
    """Cause tag for a closed live-decision position, same vocabulary as the trade-plan path's
    `classify_exit_cause` (`expected_outcome`, `risk_error`, `time_decay`, `prediction_error`).

    * no recorded return -> `unknown_return` (the price needed to tell was not available; not a win or a loss)
    * return above 0 -> `expected_outcome`
    * a loss closed by the stop rule -> `risk_error`; by the max-hold rule -> `time_decay`
    * a loss the reviewing agent closed -> `prediction_error` (the thesis it opened on did not hold)
    """
    if return_pct is None or return_pct != return_pct:
        return "unknown_return"
    if return_pct > 0:
        return "expected_outcome"
    reason = (closed_reason or "").lower()
    if reason.startswith("rule_exit:stop_loss"):
        return "risk_error"
    if reason.startswith("rule_exit:max_hold"):
        return "time_decay"
    return "prediction_error"


def _entry_of(pos: LiveDecisionOpenPosition, decisions: list[Any]) -> dict[str, Any] | None:
    for d in decisions:
        if d.trigger_id == pos.trigger_id and d.decision == "EXECUTE":
            return {"bar_ts": d.bar_ts, "reasoning": d.reasoning, "precondition_held": d.precondition_held,
                    "recorded_at": d.recorded_at}
    return None


def _reviews_of(pos: LiveDecisionOpenPosition, decisions: list[Any]) -> list[dict[str, Any]]:
    mine = [d for d in decisions if d.trigger_id == f"pos_{pos.id}"]
    return [{"bar_ts": d.bar_ts, "decision": d.decision, "reasoning": d.reasoning}
            for d in sorted(mine, key=lambda x: x.id or 0)]


def build_journal(
    backend: LiveDecisionBackend, ticker: str | None = None, strategy_id: str | None = None, limit: int = 50,
) -> dict[str, Any]:
    positions = list_closed_positions(backend, ticker, strategy_id, limit=limit)
    cache: dict[tuple[str, str], list[Any]] = {}
    entries: list[dict[str, Any]] = []
    for pos in positions:
        key = (pos.ticker, pos.strategy_id)
        if key not in cache:
            cache[key] = list_live_decisions(backend, pos.ticker, pos.strategy_id, limit=500)
        decisions = cache[key]
        held = (pos.closed_bar_ts - pos.opened_bar_ts) if pos.closed_bar_ts is not None else None
        entries.append({
            "position_id": pos.id, "ticker": pos.ticker, "strategy_id": pos.strategy_id,
            "position_size": pos.position_size,
            "entry": {**(_entry_of(pos, decisions) or {"reasoning": None}), "entry_price": pos.entry_price,
                      "opened_bar_ts": pos.opened_bar_ts, "trigger_id": pos.trigger_id},
            "reviews": _reviews_of(pos, decisions),
            "exit": {"closed_bar_ts": pos.closed_bar_ts, "reason": pos.closed_reason, "exit_price": pos.exit_price,
                     "return_pct": pos.return_pct, "held_seconds": held},
            "outcome_cause": classify_live_exit(pos.closed_reason, pos.return_pct),
        })
    return {"count": len(entries), "track_record": track_record(positions), "entries": entries}


def track_record(positions: list[LiveDecisionOpenPosition]) -> dict[str, Any]:
    """Plain counts over closed positions; the mean is over recorded returns only."""
    returns = [p.return_pct for p in positions if p.return_pct is not None and p.return_pct == p.return_pct]
    causes = Counter(classify_live_exit(p.closed_reason, p.return_pct) for p in positions)
    return {
        "n_closed": len(positions),
        "n_with_return": len(returns),
        "n_positive": sum(1 for r in returns if r > 0),
        "n_negative": sum(1 for r in returns if r < 0),
        "mean_return_pct": round(sum(returns) / len(returns), 6) if returns else None,
        "worst_return_pct": min(returns) if returns else None,
        "by_cause": dict(causes),
    }
