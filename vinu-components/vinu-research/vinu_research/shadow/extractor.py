from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone, timedelta
from typing import Any

import numpy as np

from vinu_research.shadow.models import ShadowProfile, ShadowRule

LOG = logging.getLogger(__name__)


def _parse_dt(dt_str: str) -> datetime:
    if not dt_str:
        return datetime.now(timezone.utc)
    try:
        normalized = dt_str.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    except Exception:
        return datetime.now(timezone.utc)


def _pair_trades_fifo(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sorted_rows = sorted(rows, key=lambda r: r.get("date", ""))
    roundtrips: list[dict[str, Any]] = []
    
    # Per-symbol open positions: holds {"date": date, "price": price, "shares": shares, "side": side}
    open_positions: dict[str, list[dict[str, Any]]] = {}
    
    for row in sorted_rows:
        sym = row.get("symbol", "")
        side = str(row.get("side", "BUY")).upper()
        price = float(row.get("price", 0))
        shares = float(row.get("shares", 0))
        date = row.get("date", "")
        
        if shares <= 0 or not sym:
            continue
            
        if sym not in open_positions:
            open_positions[sym] = []
        queue = open_positions[sym]
        
        if not queue:
            queue.append({
                "date": date,
                "price": price,
                "shares": shares,
                "side": side
            })
            continue
            
        pos_side = queue[0]["side"]
        if side == pos_side:
            queue.append({
                "date": date,
                "price": price,
                "shares": shares,
                "side": side
            })
        else:
            remaining_exit_shares = shares
            while queue and remaining_exit_shares > 0:
                open_pos = queue[0]
                match_shares = min(open_pos["shares"], remaining_exit_shares)
                
                entry_price = open_pos["price"]
                exit_price = price
                
                if pos_side == "BUY": # Long
                    pnl = (exit_price - entry_price) * match_shares
                    pnl_pct = (exit_price / entry_price - 1.0) if entry_price > 0 else 0.0
                else: # Short
                    pnl = (entry_price - exit_price) * match_shares
                    pnl_pct = (entry_price / exit_price - 1.0) if exit_price > 0 else 0.0
                    
                entry_dt = _parse_dt(open_pos["date"])
                exit_dt = _parse_dt(date)
                holding_days = max((exit_dt - entry_dt).days, 0)
                
                roundtrips.append({
                    "entry_date": open_pos["date"],
                    "exit_date": date,
                    "symbol": sym,
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "shares": match_shares,
                    "pnl": pnl,
                    "pnl_pct": pnl_pct,
                    "holding_days": holding_days,
                    "entry_weekday": entry_dt.weekday(),
                    "entry_hour": entry_dt.hour,
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
                    "side": side
                })
                
    return roundtrips


def _compute_features(roundtrip: dict[str, Any]) -> dict[str, float]:
    return {
        "holding_days": float(roundtrip["holding_days"]),
        "pnl_pct": float(roundtrip["pnl_pct"]),
        "entry_hour": float(roundtrip["entry_hour"]),
        "entry_weekday": float(roundtrip["entry_weekday"]),
    }


def _cluster_rules(
    roundtrips: list[dict[str, Any]],
    min_rules: int = 3,
    max_rules: int = 5,
    min_roundtrips: int = 5,
) -> list[ShadowRule]:
    if len(roundtrips) < min_roundtrips:
        LOG.warning("Not enough profitable roundtrips (%d < %d)", len(roundtrips), min_roundtrips)
        return _fallback_rules(roundtrips)

    features = np.array([list(_compute_features(r).values()) for r in roundtrips])

    from sklearn.cluster import KMeans
    from sklearn.metrics import silhouette_score

    best_k = min_rules
    best_score = -1
    for k in range(min_rules, min(max_rules, len(features)) + 1):
        km = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = km.fit_predict(features)
        if len(set(labels)) > 1:
            score = silhouette_score(features, labels)
            if score > best_score:
                best_score = score
                best_k = k

    km = KMeans(n_clusters=best_k, random_state=42, n_init=10)
    labels = km.fit_predict(features)

    rules: list[ShadowRule] = []
    processed_markets: set[str] = set()
    for cluster_idx in range(best_k):
        cluster_pts = [roundtrips[i] for i in range(len(roundtrips)) if labels[i] == cluster_idx]

        if len(cluster_pts) < 2:
            continue

        holding_days = [r["holding_days"] for r in cluster_pts]
        pnl_pcts = [r["pnl_pct"] for r in cluster_pts]
        symbols = list({r["symbol"] for r in cluster_pts if r.get("symbol")})

        lo_h = float(np.percentile(holding_days, 10))
        hi_h = float(np.percentile(holding_days, 90))
        avg_pnl = float(np.mean(pnl_pcts))

        market_key = tuple(sorted(symbols)) if symbols else ("unknown",)
        if market_key in processed_markets:
            continue
        processed_markets.add(market_key)

        rule = ShadowRule(
            rule_id=f"rule_{cluster_idx}",
            human_text=f"Hold {lo_h:.0f}-{hi_h:.0f} days in {', '.join(symbols[:3])} "
                       f"(avg PnL: {avg_pnl:+.1%})",
            entry_condition={
                "holding_days_min": lo_h,
                "holding_days_max": hi_h,
                "min_avg_pnl": avg_pnl,
            },
            exit_condition={"holding_days_range": [lo_h, hi_h]},
            holding_days_range=(lo_h, hi_h),
            weight=abs(avg_pnl),
        )
        rules.append(rule)

    return rules[:max_rules]


def _fallback_rules(roundtrips: list[dict[str, Any]]) -> list[ShadowRule]:
    if not roundtrips:
        return []
    pnl_pcts = [r["pnl_pct"] for r in roundtrips]
    holding_days = [r["holding_days"] for r in roundtrips]
    symbols = list({r["symbol"] for r in roundtrips if r.get("symbol")})
    return [
        ShadowRule(
            rule_id="rule_0",
            human_text=f"Average holding period of {np.mean(holding_days):.0f} days "
                       f"in {', '.join(symbols[:3])} "
                       f"(avg PnL: {np.mean(pnl_pcts):+.1%})",
            entry_condition={
                "holding_days_min": float(np.min(holding_days)),
                "holding_days_max": float(np.max(holding_days)),
            },
            exit_condition={},
            holding_days_range=(float(np.min(holding_days)), float(np.max(holding_days))),
            weight=abs(float(np.mean(pnl_pcts))),
        )
    ]


def extract_profile(rows: list[dict[str, Any]]) -> ShadowProfile:
    from vinu_research.shadow.storage import ShadowStorage

    journal_hash = ShadowStorage.compute_hash(rows)
    roundtrips = _pair_trades_fifo(rows)
    profitable = [r for r in roundtrips if r["pnl"] > 0]

    symbols = list({r.get("symbol", "") for r in rows if r.get("symbol")})
    profile_text = (
        f"Shadow profile from {len(rows)} journal entries, "
        f"{len(roundtrips)} roundtrips ({len(profitable)} profitable)"
    )

    rules = _cluster_rules(profitable)

    now = datetime.now(timezone.utc).isoformat()
    raw = f"shadow:{journal_hash}:{now}"
    shadow_id = f"sh_{hashlib.sha256(raw.encode()).hexdigest()[:12]}"

    return ShadowProfile(
        shadow_id=shadow_id,
        journal_hash=journal_hash,
        rules=rules,
        profile_text=profile_text,
        preferred_markets=symbols,
        created_at=now,
        updated_at=now,
        journal_entries=len(rows),
        profitable_roundtrips=len(profitable),
    )
