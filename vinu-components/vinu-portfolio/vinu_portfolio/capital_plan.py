"""Adapter between portfolio-api and the pure capital allocator (capital_allocator.py).

It gathers the inputs (the capital ledger from live-api, each strategy's return history, last prices), calls the pure
allocator, and turns the answer into the thing the daily allocation needs: dollars per strategy. All the maths stays in
capital_allocator.py; this file only fetches and reshapes.

Fails closed: when capped by a real-money base and the ledger cannot be read, or says it belongs to the other money mode,
the status is not "ok" and nobody is funded. A guess about committed money could spend money that is already spoken for.
"""
from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any, Awaitable, Callable

import pandas as pd

from vinu_infra.account_mode import current_account_mode, real_capital, reserve_fraction
from vinu_infra.capital import CapitalState
from vinu_portfolio.capital_allocator import Candidate, allocate

LOG = logging.getLogger(__name__)


def edge_stats(returns: pd.Series | None, min_history: int) -> dict[str, Any] | None:
    """Win rate, average win and average loss (positive fractions) of a strategy's return stream, ignoring flat
    periods. None when there is too little history to say anything."""
    if returns is None:
        return None
    r = returns.dropna()
    r = r[r != 0]
    if len(r) < min_history:
        return None
    wins, losses = r[r > 0], -r[r < 0]
    if wins.empty or losses.empty:
        return None
    return {"p_win": len(wins) / len(r), "n": int(len(r)), "avg_win": float(wins.mean()), "avg_loss": float(losses.mean())}


async def fetch_capital_ledger(http: Any, live_api_url: str) -> dict[str, Any] | None:
    try:
        resp = await http.get(f"{live_api_url}/live/capital")
        if resp.status_code != 200:
            return None
        data = resp.json()
        return data if isinstance(data, dict) and data.get("status") == "ok" else None
    except Exception as e:  # noqa: BLE001 -- unreadable ledger means "refuse", handled by the caller
        LOG.warning("Capital ledger unavailable: %s", e)
        return None


async def build_capital_plan(
    *,
    http: Any,
    config: Any,
    tilted: list[dict[str, Any]],
    strategies_by_name: dict[str, dict[str, Any]],
    returns_for: Callable[[dict[str, Any]], Awaitable[pd.Series | None]],
    price_for: Callable[[str], Awaitable[float | None]],
    free_cash_scale: float,
) -> dict[str, Any]:
    base = real_capital()
    mode = current_account_mode()
    if base is None:
        return {"status": "not_capped"}
    ledger = await fetch_capital_ledger(http, config.live_api_url)
    if ledger is None:
        return {"status": "capital_ledger_unavailable", "account_mode": mode, "capital_base": base}
    if ledger.get("account_mode") != mode or not ledger.get("capped"):
        return {"status": "account_mode_mismatch", "account_mode": mode, "capital_base": base,
                "ledger_account_mode": ledger.get("account_mode"), "ledger_capped": ledger.get("capped")}

    committed = float(ledger.get("committed") or 0.0)
    state = CapitalState(mode, base, committed, reserve_fraction())
    held_by_symbol: dict[str, float] = {}
    for p in ledger.get("open_positions") or []:
        sym = str(p.get("symbol", "")).upper()
        held_by_symbol[sym] = held_by_symbol.get(sym, 0.0) + float(p.get("cost") or 0.0)

    candidates: list[Candidate] = []
    skipped: list[dict[str, Any]] = []
    name_of: dict[str, str] = {}
    held_of: dict[str, float] = {}
    for t in tilted:
        name = t["name"]
        symbol = str(t.get("symbol") or name).upper()
        held = held_by_symbol.pop(symbol, 0.0)   # a symbol's held money belongs to the first strategy on it
        held_of[name] = held
        stats = edge_stats(await returns_for(strategies_by_name.get(name, t)), config.capital_min_history)
        if stats is None:
            skipped.append({"ticker": symbol, "strategy": name, "reason": "not_enough_history"})
            continue
        price = await price_for(symbol)
        candidates.append(Candidate(
            ticker=symbol, price=price, p_win=stats["p_win"], n_trades=stats["n"], avg_win=stats["avg_win"],
            avg_loss=stats["avg_loss"], round_trip_cost=0.0,   # the simulator's returns already include trading costs
            fractional=config.capital_fractional_shares, artifact_id=str(strategies_by_name.get(name, {}).get("artifact_id", "")),
            held=held,
        ))
        name_of[symbol] = name

    plan = allocate(state, candidates, kelly_scale=config.capital_kelly_scale,
                    max_position_pct=config.capital_max_position_pct, free_cash_scale=free_cash_scale)

    # Dollars each strategy should hold after this plan: the funded target, or what it already holds when the
    # allocator had no new money for it (a held position is never sold off just because the maths found no edge today).
    target_dollars: dict[str, float] = {}
    funded_by_symbol = {f.ticker: f for f in plan.funded}
    for t in tilted:
        name = t["name"]
        symbol = str(t.get("symbol") or name).upper()
        f = funded_by_symbol.get(symbol)
        target_dollars[name] = f.target_total if f is not None and name_of.get(symbol) == name else held_of.get(name, 0.0)
    return {
        "status": "ok", "account_mode": mode, "capital_base": base, "committed": committed,
        "ledger": {k: ledger.get(k) for k in ("free_cash", "reserve", "reserve_fraction", "over_committed", "results")},
        "plan": asdict(plan), "skipped": skipped, "target_dollars": target_dollars,
        "deployable_total": round(sum(target_dollars.values()), 4), "free_cash_scale": free_cash_scale,
    }
