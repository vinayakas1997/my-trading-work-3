from __future__ import annotations

from typing import Any

from vinu_live.book.schema import Position


def per_symbol_exposure(
    positions: list[Position],
    prices: dict[str, float],
) -> dict[str, float]:
    exposure: dict[str, float] = {}
    for pos in positions:
        price = prices.get(pos.symbol)
        if price is None:
            continue
        value = pos.qty * price * (1 if pos.side == "long" else -1)
        exposure[pos.symbol] = exposure.get(pos.symbol, 0.0) + value
    return exposure


def per_cluster_exposure(
    positions: list[Position],
    prices: dict[str, float],
    cluster_map: dict[str, str],
) -> dict[str, float]:
    cluster_exposure: dict[str, float] = {}
    for pos in positions:
        price = prices.get(pos.symbol)
        if price is None:
            continue
        cluster = cluster_map.get(pos.symbol, "other")
        value = pos.qty * price * (1 if pos.side == "long" else -1)
        cluster_exposure[cluster] = cluster_exposure.get(cluster, 0.0) + value
    return cluster_exposure


def portfolio_total_exposure(
    positions: list[Position],
    prices: dict[str, float],
) -> float:
    total = 0.0
    for pos in positions:
        price = prices.get(pos.symbol)
        if price is None:
            continue
        total += pos.qty * price * (1 if pos.side == "long" else -1)
    return total


def portfolio_gross_exposure(
    positions: list[Position],
    prices: dict[str, float],
) -> float:
    total = 0.0
    for pos in positions:
        price = prices.get(pos.symbol)
        if price is None:
            continue
        total += pos.qty * price
    return total


def portfolio_net_exposure(
    positions: list[Position],
    prices: dict[str, float],
) -> float:
    long = 0.0
    short = 0.0
    for pos in positions:
        price = prices.get(pos.symbol)
        if price is None:
            continue
        value = pos.qty * price
        if pos.side == "long":
            long += value
        else:
            short += value
    return long - short


def exposure_summary(
    positions: list[Position],
    prices: dict[str, float],
    cluster_map: dict[str, str] | None = None,
) -> dict[str, Any]:
    cluster_map = cluster_map or {}
    return {
        "total_exposure": portfolio_total_exposure(positions, prices),
        "gross_exposure": portfolio_gross_exposure(positions, prices),
        "net_exposure": portfolio_net_exposure(positions, prices),
        "per_symbol": per_symbol_exposure(positions, prices),
        "per_cluster": per_cluster_exposure(positions, prices, cluster_map),
        "position_count": len(positions),
        "long_count": sum(1 for p in positions if p.side == "long"),
        "short_count": sum(1 for p in positions if p.side == "short"),
    }
