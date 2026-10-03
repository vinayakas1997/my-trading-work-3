"""Execution-quality guards shared between TradePlanOrchestrator's signal-driven
entries and LiveScheduler's portfolio-rebalance TWAP/VWAP path.

Before this module existed, the spread gate and event-risk blackout only lived
inline in orchestrator.py -- LiveScheduler's `_execute_plan` fired straight to
the broker with no risk gates at all. Both call sites want the exact same
fail-open behaviour (a quote/calendar fetch problem never blocks a trade), so
the checks are written once here as small async functions over a plain
`httpx.AsyncClient` + base URL, not methods on either caller's class.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from vinu_infra.pipeline_edge_recorder import record_edge

LOG = logging.getLogger(__name__)

HALT_FILE_PATH = Path.home() / ".vinu-live" / "HALT"


def instruction_increases_exposure(side: str, qty: float, current_qty: float) -> bool:
    """True when filling this instruction moves the position FURTHER from flat
    (opens, adds to, or flips through zero into a larger opposite position);
    False for anything that only shrinks or closes it.

    The entries-only guards (cooldown, stale data, turbulence) must never hold
    back a risk-reducing order -- see logic-audit-2026-10-02 A5 -- so every
    caller classifies an instruction with this before gating it. Pure and
    total: a side other than buy/sell cannot be classified, so it is treated
    as increasing and the caller decides what to do with it."""
    s = (side or "").lower()
    if s not in ("buy", "sell"):
        return True
    delta = qty if s == "buy" else -qty
    return abs(current_qty + delta) > abs(current_qty)


def spread_bps_from_quote(payload: Any) -> float | None:
    """Basis-point spread from a vinu-stock-price /stock/quote payload, or
    None (never blocks) when the payload is missing / not `ok` / unparseable
    / negative -- fail-open, same posture as every other data-quality guard
    in this package."""
    if not isinstance(payload, dict) or not payload.get("ok"):
        return None
    try:
        sb = float(payload.get("spread_bps"))
    except (TypeError, ValueError):
        return None
    if sb < 0.0:
        return None
    return sb


async def fetch_quote_snapshot(http: Any, stock_price_api_url: str, symbol: str) -> tuple[float | None, float | None]:
    """(spread in basis points, mid price) from one quote call; each None when unavailable (fail-open, same parse as
    spread_bps_from_quote). The mid is what slippage is measured against."""
    payload: Any = None
    try:
        resp = await http.get(f"{stock_price_api_url}/stock/quote/{symbol}")
        if getattr(resp, "status_code", None) == 200:
            payload = resp.json()
    except Exception as e:  # noqa: BLE001
        LOG.debug("Quote fetch failed for %s, failing open: %s", symbol, e)
    mid = None
    if isinstance(payload, dict) and payload.get("ok"):
        try:
            m = float(payload.get("mid"))
            mid = m if m > 0 else None
        except (TypeError, ValueError):
            mid = None
    return spread_bps_from_quote(payload), mid


async def fetch_spread_bps(http: Any, stock_price_api_url: str, symbol: str) -> float | None:
    """The live NBBO spread for `symbol` in basis points, or None (fail-open)
    on any fetch/parse problem. Split out from spread_gate_reason so a
    caller that also needs the raw number (e.g. to pick market vs. limit
    order type from how much of a slippage budget crossing the spread would
    spend) fetches it once, not twice."""
    payload: Any = None
    try:
        resp = await http.get(f"{stock_price_api_url}/stock/quote/{symbol}")
        if getattr(resp, "status_code", None) == 200:
            payload = resp.json()
    except Exception as e:  # noqa: BLE001 -- fail-open on any fetch error
        LOG.debug("Spread fetch failed for %s, failing open: %s", symbol, e)
    return spread_bps_from_quote(payload)


def spread_gate_reason_from_bps(spread_bps: float | None, max_spread_bps: float) -> str | None:
    """None if the trade may proceed, else a human-readable block reason,
    given an already-fetched spread. 0 (or negative) `max_spread_bps`
    disables the gate entirely."""
    if max_spread_bps <= 0:
        return None
    if spread_bps is not None and spread_bps > max_spread_bps:
        return f"spread {spread_bps:.1f}bps exceeds max {max_spread_bps:.1f}bps"
    return None


async def spread_gate_reason(
    http: Any, stock_price_api_url: str, symbol: str, max_spread_bps: float,
) -> str | None:
    """None if the trade may proceed, else a human-readable block reason.
    0 (or negative) `max_spread_bps` disables the gate entirely. Fail-open
    on any quote fetch problem. Convenience wrapper over fetch_spread_bps +
    spread_gate_reason_from_bps for a caller that only needs the gate
    decision, not the raw spread."""
    if max_spread_bps <= 0:
        return None
    spread = await fetch_spread_bps(http, stock_price_api_url, symbol)
    return spread_gate_reason_from_bps(spread, max_spread_bps)


async def event_blackout_reason(
    http: Any, stock_price_api_url: str, symbol: str, blackout_hours: float,
) -> str | None:
    """None if the trade may proceed, else a human-readable block reason.
    0 (or negative) `blackout_hours` disables the gate entirely. Fail-open
    on any calendar fetch problem (service down, no key, no rows)."""
    if blackout_hours <= 0:
        return None
    try:
        resp = await http.get(
            f"{stock_price_api_url}/stock/events/{symbol}",
            params={"within_hours": blackout_hours},
        )
        if getattr(resp, "status_code", None) == 200:
            body = resp.json()
            if isinstance(body, dict) and body.get("blackout"):
                rows = body.get("events") or []
                return (rows[0].get("title") if rows else "") or "event within blackout window"
    except Exception as e:  # noqa: BLE001 -- fail-open on any fetch error
        LOG.debug("Event blackout check failed for %s, failing open: %s", symbol, e)
    return None


async def halt_reason(http: Any, agent_api_url: str, edge_id: str | None = None) -> str | None:
    """None if trading may proceed, else a human-readable block reason.

    There are two independent kill-switch sources in this stack:
    (1) the local filesystem sentinel (~/.vinu-live/HALT, an operator
        dropping a file on this host), and
    (2) the agent's cross-process halt flag (GET /agent/broker/status,
        engaged by emergency_flatten / the breaker / the OOD auto-halt in
        orchestrator.py).
    They used to be checked in only one place each -- LiveScheduler read
    only the local file, TradePlanOrchestrator read only the remote flag --
    so an operator dropping the HALT file believed it stopped everything
    but the orchestrator kept placing entries, and a breaker/OOD-engaged
    remote halt didn't stop the scheduler's TWAP/VWAP loop cleanly. Both
    callers now check both sources through this one function.

    `edge_id` (Phase 3 runtime recorder): when given, the remote status read is recorded
    as that pipeline edge -- `received` on a 200, `missing` on a non-200 or an exception
    (the fail-open case below, which used to leave no trace). Observe-only; never raises.

    Fail-open on the remote check only (an unreachable agent means no order
    can be placed anyway, same posture as the orchestrator's prior
    `_is_trading_halted`); the local file check is a plain `Path.exists()`
    and cannot silently miss.
    """
    if HALT_FILE_PATH.exists():
        return f"HALT file present at {HALT_FILE_PATH}"
    try:
        resp = await http.get(f"{agent_api_url}/agent/broker/status")
        if getattr(resp, "status_code", None) == 200:
            if edge_id:
                record_edge(edge_id, "received")
            if bool((resp.json() or {}).get("halted")):
                return "agent kill switch engaged (GET /agent/broker/status)"
        elif edge_id:
            record_edge(edge_id, "missing", f"GET /agent/broker/status -> HTTP {getattr(resp, 'status_code', '?')}")
    except Exception as e:  # noqa: BLE001 -- fail-open on any fetch error
        LOG.debug("Remote halt-status check failed, failing open: %s", e)
        if edge_id:
            record_edge(edge_id, "missing", f"GET /agent/broker/status failed: {e}")
    return None
