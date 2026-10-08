"""Capital allocator: the self-isolated money maths (plan: Proper-Project-Implementation/05-handling-system-portfolio-allocator).

A pure calculation. It imports nothing from the rest of this package (only the shared free-cash definition in vinu-infra), reads no database and calls no service, so the same
inputs always give the same answer. The capital base is `real_capital` (for example 20 dollars), never the paper balance.
Every plan carries the `account_mode` tag it was computed for; a paper plan and a real plan are never combined.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from vinu_infra.capital import CapitalState  # noqa: F401 -- the shared free-cash definition, re-exported


@dataclass(frozen=True)
class Candidate:
    ticker: str
    price: float | None  # None = unknown: no whole-share check, the amount stands
    p_win: float                 # raw win rate of the strategy's trades
    n_trades: int                # how many trades that rate comes from
    avg_win: float               # average winning trade, as a fraction of the position (0.03 = 3 %)
    avg_loss: float              # average losing trade, as a positive fraction of the position
    round_trip_cost: float = 0.0  # fraction of the position lost to spread and slippage per round trip
    fractional: bool = True      # can this ticker be bought in fractions of a share
    artifact_id: str = ""
    held: float = 0.0            # money already held in this candidate's symbol, at cost


@dataclass(frozen=True)
class Funded:
    ticker: str
    artifact_id: str
    amount: float                # NEW money to put in (0 when the position is already at or above its target)
    shares: float | None         # whole or fractional shares for the new money; None when the price is unknown
    held: float                  # money already held at cost
    target_total: float          # held + amount: what the position should hold after this plan
    edge: float                  # expected return per dollar after costs
    kelly_position_fraction: float
    cash_after_loss: float       # free cash left if this trade loses its average loss
    cash_after_win: float        # free cash left if it wins its average win


@dataclass(frozen=True)
class AllocationPlan:
    account_mode: str
    real_capital: float
    committed: float
    reserve: float
    free_cash_before: float
    funded: list[Funded] = field(default_factory=list)
    refused: list[dict] = field(default_factory=list)
    free_cash_after: float = 0.0


def shrunk_p_win(p_win: float, n_trades: int, prior_trades: int = 20) -> float:
    """Win rate pulled toward 50 % when there are few trades (a Beta(prior/2, prior/2) prior): 30 trades is a thin
    sample, and the raw rate flatters."""
    n = max(0, int(n_trades))
    wins = max(0.0, min(1.0, p_win)) * n
    half = prior_trades / 2.0
    return (wins + half) / (n + prior_trades)


def net_payoffs(c: Candidate) -> tuple[float, float]:
    """(win, loss) per dollar of position after the round-trip cost."""
    return c.avg_win - c.round_trip_cost, c.avg_loss + c.round_trip_cost


def expected_edge(c: Candidate, p: float) -> float:
    win, loss = net_payoffs(c)
    return p * win - (1.0 - p) * loss


def kelly_position_fraction(c: Candidate, p: float) -> float:
    """Full-Kelly share of the bankroll to put into the position when a win gains `win` and a loss costs `loss` per
    dollar: f = p / loss - q / win. Zero or negative means no edge."""
    win, loss = net_payoffs(c)
    if win <= 0 or loss <= 0:
        return 0.0
    return p / loss - (1.0 - p) / win


def allocate(
    state: CapitalState,
    candidates: list[Candidate],
    *,
    kelly_scale: float = 0.25,
    max_position_pct: float = 0.25,
    prior_trades: int = 20,
    free_cash_scale: float = 1.0,
) -> AllocationPlan:
    """Fund the candidates with the best expected return per dollar first, each sized by fractional Kelly and capped
    by the position limit and by the free cash that is left. Nothing here can spend more than the free cash."""
    free = state.free_cash * max(0.0, min(1.0, free_cash_scale))
    plan_funded: list[Funded] = []
    refused: list[dict] = []
    ranked: list[tuple[float, float, Candidate]] = []
    for c in candidates:
        if (c.price is not None and c.price <= 0) or c.avg_win <= 0 or c.avg_loss <= 0:
            refused.append({"ticker": c.ticker, "reason": "invalid_inputs"})
            continue
        p = shrunk_p_win(c.p_win, c.n_trades, prior_trades)
        edge = expected_edge(c, p)
        if edge <= 0:
            refused.append({"ticker": c.ticker, "reason": "no_edge_after_costs", "edge": round(edge, 6)})
            continue
        f = kelly_position_fraction(c, p)
        if f <= 0:
            refused.append({"ticker": c.ticker, "reason": "no_kelly_edge"})
            continue
        ranked.append((edge, f, c))
    ranked.sort(key=lambda t: t[0], reverse=True)

    remaining = free
    for edge, f, c in ranked:
        target = min(f * kelly_scale, max_position_pct) * state.real_capital
        amount = min(max(0.0, target - c.held), remaining)
        if c.price is None:
            shares, spend = None, amount
        else:
            if c.fractional:
                shares = math.floor(amount / c.price * 1e6) / 1e6
            else:
                shares = float(math.floor(amount / c.price))
            spend = shares * c.price
        if spend <= 0:
            if c.held > 0:   # already holding as much as the target allows: keep it, add nothing
                plan_funded.append(Funded(
                    ticker=c.ticker, artifact_id=c.artifact_id, amount=0.0, shares=0.0 if c.price else None,
                    held=round(c.held, 4), target_total=round(c.held, 4), edge=round(edge, 6),
                    kelly_position_fraction=round(f, 6), cash_after_loss=round(remaining, 4), cash_after_win=round(remaining, 4),
                ))
            else:
                refused.append({"ticker": c.ticker, "reason": "price_above_available_funds" if amount > 0 else "no_free_cash",
                                "price": c.price, "available": round(remaining, 2)})
            continue
        win, loss = net_payoffs(c)
        plan_funded.append(Funded(
            ticker=c.ticker, artifact_id=c.artifact_id, amount=round(spend, 4), shares=shares,
            held=round(c.held, 4), target_total=round(c.held + spend, 4), edge=round(edge, 6),
            kelly_position_fraction=round(f, 6),
            cash_after_loss=round(remaining - spend + spend * (1.0 - loss), 4),
            cash_after_win=round(remaining - spend + spend * (1.0 + win), 4),
        ))
        remaining -= spend
    return AllocationPlan(
        account_mode=state.account_mode, real_capital=state.real_capital, committed=state.committed,
        reserve=round(state.reserve, 4), free_cash_before=round(free, 4), funded=plan_funded, refused=refused,
        free_cash_after=round(remaining, 4),
    )
