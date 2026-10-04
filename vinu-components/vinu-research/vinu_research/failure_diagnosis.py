"""Why did a strategy fail? One deterministic answer from numbers the system already has.

A backtest reports a Sharpe and a list of failed tests, but not the reason. Running the same attempt twice, once with the
simulator's trading costs and once with none, separates the three causes that look identical in the net numbers:

* `no_edge`              -- it does not make money even when trading is free (the idea itself has nothing),
* `edge_eaten_by_costs`  -- it makes money when trading is free but the costs take all of it (too many trades for the
                            size of the edge, typical of short bar sizes),
* `works_after_costs`    -- it survives costs (this says nothing about whether the edge is real: see `too_few_trades`).

`too_few_trades` is a separate flag, not a verdict: a Sharpe built on a handful of trades is not evidence either way.

Thresholds are two named constants. They are choices, not facts: a Sharpe of 0.1 is "indistinguishable from zero" for these
sample sizes. Nothing here predicts anything; it only explains an observed result, in the numbers it was given.
"""

from __future__ import annotations

from dataclasses import dataclass, field

EDGE_FLOOR_SHARPE = 0.1      # at or below this a Sharpe is treated as "no edge"
MIN_TRADES = 30              # below this the result is too thin to judge


@dataclass
class Diagnosis:
    verdict: str
    net_sharpe: float
    gross_sharpe: float
    net_return: float
    gross_return: float
    trade_count: int
    too_few_trades: bool
    reasons: list[str] = field(default_factory=list)

    @property
    def cost_drag_return(self) -> float:
        """Return lost to trading costs: free-trading return minus real return."""
        return self.gross_return - self.net_return


def diagnose(
    *, net_sharpe: float, gross_sharpe: float, net_return: float, gross_return: float, trade_count: int,
    edge_floor: float = EDGE_FLOOR_SHARPE, min_trades: int = MIN_TRADES,
) -> Diagnosis:
    """`gross_*` come from the same attempt re-run with zero transaction cost and zero slippage."""
    thin = trade_count < min_trades
    if gross_sharpe <= edge_floor:
        verdict = "no_edge"
        reasons = [
            f"even with free trading the Sharpe is {gross_sharpe:.2f} (return {gross_return:+.1%}), "
            f"at or below {edge_floor:.1f}: the idea itself shows no edge, so costs are not the cause",
        ]
        if net_sharpe < gross_sharpe:
            reasons.append(f"costs then made it worse: Sharpe {net_sharpe:.2f}, return {net_return:+.1%}")
    elif net_sharpe <= edge_floor:
        verdict = "edge_eaten_by_costs"
        reasons = [
            f"with free trading it earns Sharpe {gross_sharpe:.2f} (return {gross_return:+.1%}), "
            f"but after costs Sharpe {net_sharpe:.2f} (return {net_return:+.1%})",
            f"costs removed {gross_return - net_return:.1%} of return over {trade_count} trades: "
            "the edge per trade is smaller than the cost per trade",
        ]
    else:
        verdict = "works_after_costs"
        reasons = [
            f"survives costs: Sharpe {net_sharpe:.2f} after costs against {gross_sharpe:.2f} with free trading "
            f"(costs took {gross_return - net_return:.1%} of return)",
        ]
    if thin:
        reasons.append(f"only {trade_count} trades (fewer than {min_trades}): too few to judge either way")
    return Diagnosis(verdict, net_sharpe, gross_sharpe, net_return, gross_return, trade_count, thin, reasons)


def diagnose_across(per_symbol: dict[str, Diagnosis], agree: float = 0.8) -> dict:
    """Is the result about the idea or about the ticker? `consistent` when at least `agree` of the tickers share one
    verdict; otherwise the idea works on some and not others, and the split is returned."""
    if not per_symbol:
        return {"consistency": "no_data", "verdicts": {}, "majority": None}
    counts: dict[str, list[str]] = {}
    for sym, d in per_symbol.items():
        counts.setdefault(d.verdict, []).append(sym)
    majority, members = max(counts.items(), key=lambda kv: len(kv[1]))
    share = len(members) / len(per_symbol)
    return {
        "consistency": "consistent" if share >= agree else "ticker_specific",
        "majority": majority,
        "share": share,
        "verdicts": {v: sorted(s) for v, s in counts.items()},
    }


def explain(d: Diagnosis) -> str:
    """Plain-English paragraph for the report and summary; only the numbers in `d`."""
    head = {
        "no_edge": "WHY IT FAILED: the idea shows no edge.",
        "edge_eaten_by_costs": "WHY IT FAILED: there is an edge, but trading costs eat it.",
        "works_after_costs": "WHY IT DID NOT FAIL ON COSTS: the result survives trading costs.",
    }[d.verdict]
    return head + " " + "; ".join(d.reasons) + "."
