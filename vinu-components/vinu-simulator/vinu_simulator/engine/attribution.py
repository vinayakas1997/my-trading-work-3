from __future__ import annotations

from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd


def match_trades(trades: list[Any]) -> list[dict[str, Any]]:
    def get_date(item: Any) -> Any:
        if hasattr(item, "date"):
            return item.date
        if isinstance(item, dict):
            return item.get("date") or item.get("timestamp") or ""
        return ""

    sorted_trades = sorted(trades, key=get_date)
    
    round_trips = []
    # Queue of open transactions per symbol
    open_positions: dict[str, list[dict[str, Any]]] = {}
    
    for t in sorted_trades:
        sym = t.symbol if hasattr(t, "symbol") else t.get("symbol", "?")
        side = t.side if hasattr(t, "side") else t.get("side", "BUY")
        price = float(t.price if hasattr(t, "price") else t.get("price", 0.0))
        shares = float(t.shares if hasattr(t, "shares") else t.get("shares", 0.0))
        cost = float(t.cost if hasattr(t, "cost") else t.get("cost", 0.0))
        date = get_date(t)
        trade_id = t.trade_id if hasattr(t, "trade_id") else (t.get("trade_id") if isinstance(t, dict) else str(id(t)))
        
        if shares <= 0:
            continue
            
        cost_per_share = cost / shares if shares > 0 else 0.0
        
        if sym not in open_positions:
            open_positions[sym] = []
            
        queue = open_positions[sym]
        
        if not queue:
            queue.append({
                "date": date,
                "price": price,
                "shares": shares,
                "cost_per_share": cost_per_share,
                "side": side,
                "trade_id": trade_id
            })
            continue
            
        pos_side = queue[0]["side"]
        
        if side == pos_side:
            queue.append({
                "date": date,
                "price": price,
                "shares": shares,
                "cost_per_share": cost_per_share,
                "side": side,
                "trade_id": trade_id
            })
        else:
            remaining_exit_shares = shares
            
            while queue and remaining_exit_shares > 0:
                open_pos = queue[0]
                match_shares = min(open_pos["shares"], remaining_exit_shares)
                
                entry_price = open_pos["price"]
                entry_cost_part = open_pos["cost_per_share"] * match_shares
                exit_cost_part = cost_per_share * match_shares
                
                if pos_side == "BUY": # Long
                    pnl = (price - entry_price) * match_shares - entry_cost_part - exit_cost_part
                else: # Short
                    pnl = (entry_price - price) * match_shares - entry_cost_part - exit_cost_part
                    
                round_trips.append({
                    "symbol": sym,
                    "entry_date": open_pos["date"],
                    "exit_date": date,
                    "side": "LONG" if pos_side == "BUY" else "SHORT",
                    "shares": match_shares,
                    "entry_price": entry_price,
                    "exit_price": price,
                    "pnl": pnl,
                    "entry_cost": entry_cost_part,
                    "exit_cost": exit_cost_part,
                    "exit_trade_id": trade_id,
                })
                
                open_pos["shares"] -= match_shares
                remaining_exit_shares -= match_shares
                
                if open_pos["shares"] <= 1e-10:
                    queue.pop(0)
                    
            if remaining_exit_shares > 1e-10:
                queue.append({
                    "date": date,
                    "price": price,
                    "shares": remaining_exit_shares,
                    "cost_per_share": cost_per_share,
                    "side": side,
                    "trade_id": trade_id
                })
                
    return round_trips


def by_symbol_stats(
    trades: list[Any],
    *,
    round_trips: list[dict[str, Any]] | None = None,
) -> dict[str, dict[str, float]]:
    if round_trips is None:
        round_trips = match_trades(trades)
    symbols: dict[str, list[float]] = {}
    for rt in round_trips:
        sym = rt["symbol"]
        if sym not in symbols:
            symbols[sym] = []
        symbols[sym].append(rt["pnl"])

    result: dict[str, dict[str, float]] = {}
    for sym, pnls in symbols.items():
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]
        total_pnl = sum(pnls)
        result[sym] = {
            "count": len(pnls),
            "win_count": len(wins),
            "loss_count": len(losses),
            "win_rate": len(wins) / len(pnls) if pnls else 0.0,
            "total_pnl": total_pnl,
            "avg_pnl": total_pnl / len(pnls) if pnls else 0.0,
            "avg_win": sum(wins) / len(wins) if wins else 0.0,
            "avg_loss": sum(losses) / len(losses) if losses else 0.0,
        }
    return result


def by_exit_reason_stats(
    trades: list[Any],
    exit_reasons: dict[str, str] | None = None,
) -> dict[str, dict[str, float]]:
    if exit_reasons is None:
        exit_reasons = {}
    
    round_trips = match_trades(trades)
    reasons: dict[str, list[float]] = {}
    
    for rt in round_trips:
        exit_trade_id = rt["exit_trade_id"]
        reason = exit_reasons.get(exit_trade_id, "unknown")
        if reason not in reasons:
            reasons[reason] = []
        reasons[reason].append(rt["pnl"])

    result: dict[str, dict[str, float]] = {}
    for reason, pnls in reasons.items():
        total_pnl = sum(pnls)
        result[reason] = {
            "count": len(pnls),
            "total_pnl": total_pnl,
            "avg_pnl": total_pnl / len(pnls) if pnls else 0.0,
        }
    return result


def beta_regression(
    strategy_returns: pd.Series,
    benchmark_returns: pd.Series,
    risk_free_rate: float = 0.0,
    periods_per_year: float = 252.0,
) -> dict[str, float]:
    aligned = pd.concat([strategy_returns, benchmark_returns], axis=1).dropna()
    if len(aligned) < 10:
        return {}

    strat = aligned.iloc[:, 0]
    bench = aligned.iloc[:, 1]
    n = len(strat)

    beta = float(strat.cov(bench) / bench.var()) if bench.var() > 0 else 0.0
    rf_daily = (1 + risk_free_rate) ** (1 / periods_per_year) - 1
    excess_strat = strat.mean() - rf_daily
    excess_bench = bench.mean() - rf_daily
    alpha_daily = excess_strat - beta * excess_bench
    alpha = alpha_daily * periods_per_year

    excess_ret = strat - bench
    tracking_error = float(excess_ret.std() * np.sqrt(periods_per_year))
    info_ratio = (
        float((strat.mean() - bench.mean()) / excess_ret.std() * np.sqrt(periods_per_year))
        if excess_ret.std() > 0
        else 0.0
    )
    correlation = float(strat.corr(bench))
    r_squared = correlation**2

    return {
        "alpha": alpha,
        "beta": beta,
        "r_squared": r_squared,
        "correlation": correlation,
        "tracking_error": tracking_error,
        "information_ratio": info_ratio,
        "n_observations": n,
    }
