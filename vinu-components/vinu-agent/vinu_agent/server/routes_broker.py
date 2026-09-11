"""HTTP-exposed kill switch — the networked front door onto broker/kill_switch.py.

Every vinu-* service runs in its own container with a private tmpfs /tmp
(see docker-compose.yml), so a kill switch based on touching a local file is
only ever visible within the one container that touched it. OrderGuard checks
the kill switch from inside agent-api, so any other service (vinu-portfolio's
drawdown monitor, a human operator, a future automated monitor) that needs to
halt trading has to do it through this HTTP endpoint, not by touching a file
of its own.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from ..broker.factory import get_live_broker
from ..broker.kill_switch import halt_trading, is_trading_halted, resume_trading
from ..broker.performance_store import get_store
from ..tools.trade_tool import TradeTool

router = APIRouter()


class HaltRequest(BaseModel):
    scope: str | None = None
    reason: str | None = None


class ResumeRequest(BaseModel):
    scope: str | None = None


@router.post("/broker/halt")
async def broker_halt(body: HaltRequest = HaltRequest()) -> dict[str, Any]:
    halt_trading(scope=body.scope)
    return {"status": "ok", "halted": True, "scope": body.scope, "reason": body.reason}


@router.post("/broker/resume")
async def broker_resume(body: ResumeRequest = ResumeRequest()) -> dict[str, Any]:
    resume_trading(scope=body.scope)
    return {"status": "ok", "halted": False, "scope": body.scope}


@router.get("/broker/status")
async def broker_status(scope: str | None = None) -> dict[str, Any]:
    return {"halted": is_trading_halted(scope=scope), "scope": scope}


class MandateRenewRequest(BaseModel):
    days: float | None = None       # renew consent for this many days from now
    until: str | None = None        # ...or set an explicit ISO-8601 expiry


@router.get("/broker/mandate")
async def broker_get_mandate() -> dict[str, Any]:
    from ..broker.mandate import TradingMandate

    return {"mandate": TradingMandate.load().to_dict()}


@router.post("/broker/mandate/renew")
async def broker_renew_mandate(body: MandateRenewRequest = MandateRenewRequest()) -> dict[str, Any]:
    """C18: bump the mandate's consent expiry without a restart. Writes only
    the `consent_expires_at` key back into mandate.yaml, preserving the rest;
    every subsequent `TradingMandate.load()` (OrderGuard builds one per
    order) picks it up."""
    from datetime import datetime, timedelta, timezone

    import yaml as _yaml
    from fastapi import HTTPException

    from ..broker.kill_switch import AuditLogger
    from ..broker.mandate import DEFAULT_MANDATE_PATH

    if body.until:
        try:
            expiry = datetime.fromisoformat(body.until.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(status_code=422, detail=f"`until` is not a valid ISO timestamp: {body.until!r}")
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
    else:
        days = body.days if body.days and body.days > 0 else 30.0
        expiry = datetime.now(timezone.utc) + timedelta(days=days)

    path = DEFAULT_MANDATE_PATH
    try:
        raw = _yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}
    except Exception:
        raw = {}
    raw = raw or {}
    raw["consent_expires_at"] = expiry.isoformat()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_yaml.safe_dump(raw, sort_keys=True), encoding="utf-8")
    AuditLogger.log("mandate_consent_renewed", {"consent_expires_at": raw["consent_expires_at"]})
    return {"status": "ok", "consent_expires_at": raw["consent_expires_at"]}


class SymbolOverrideRequest(BaseModel):
    state: str  # "untradeable" | "reduce_only" | "ignored"
    reason: str = ""
    set_by: str = ""


@router.get("/broker/overrides")
async def broker_list_overrides() -> dict[str, Any]:
    from ..broker.symbol_overrides import get_override_store

    return {"overrides": [r.to_dict() for r in get_override_store().all()]}


@router.put("/broker/overrides/{symbol}")
async def broker_set_override(symbol: str, body: SymbolOverrideRequest) -> dict[str, Any]:
    from fastapi import HTTPException

    from ..broker.guard_codes import OverrideState
    from ..broker.symbol_overrides import InvalidOverrideTransition, get_override_store

    try:
        state = OverrideState(body.state)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"unknown override state {body.state!r}")
    try:
        rec = get_override_store().set(symbol, state, reason=body.reason, set_by=body.set_by)
    except InvalidOverrideTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"status": "ok", "override": rec.to_dict()}


@router.delete("/broker/overrides/{symbol}")
async def broker_clear_override(symbol: str) -> dict[str, Any]:
    from ..broker.symbol_overrides import get_override_store

    cleared = get_override_store().clear(symbol)
    return {"status": "ok", "cleared": cleared, "symbol": symbol.upper()}


@router.get("/broker/safety-ledger")
async def broker_safety_ledger(limit: int = 100) -> dict[str, Any]:
    """A37: the tamper-evident halt/resume record + a chain-integrity check.
    `verified.ok` is False (with `broken_at`) if any past entry was altered,
    reordered, or deleted."""
    from ..broker.audit_ledger import get_safety_ledger

    ledger = get_safety_ledger()
    verification = ledger.verify()
    entries = ledger.entries()
    return {
        "verified": {
            "ok": verification.ok,
            "entries": verification.entries,
            "broken_at": verification.broken_at,
            "reason": verification.reason,
        },
        "entries": entries[-limit:] if limit and limit > 0 else entries,
    }


@router.get("/broker/account")
async def broker_account() -> dict[str, Any]:
    """Current account equity — the one place other services (e.g. vinu-portfolio's
    drawdown monitor) should get this from, rather than each holding its own
    broker credentials. Returns configured=False (not an error) until a broker
    account exists, so callers can treat that as "no signal yet", not a failure.
    """
    broker = get_live_broker()
    if not broker.is_configured():
        return {"configured": False, "equity": None, "cash": None}
    try:
        account = broker.get_account()
        return {
            "configured": True,
            "equity": account.equity,
            "cash": account.cash,
            "portfolio_value": account.portfolio_value,
        }
    except Exception as e:
        return {"configured": True, "equity": None, "cash": None, "error": str(e)}


@router.get("/broker/positions")
async def broker_positions() -> list[dict[str, Any]]:
    broker = get_live_broker()
    if not broker.is_configured():
        return []
    positions = await asyncio.to_thread(broker.get_positions)
    return [asdict(p) for p in positions]


class OrderRequest(BaseModel):
    symbol: str
    side: str
    qty: float
    order_type: str = "market"
    limit_price: float | None = None
    stop_price: float | None = None
    time_in_force: str = "day"
    take_profit_price: float | None = None
    stop_loss_price: float | None = None
    stop_loss_limit_price: float | None = None
    reduce_only: bool = False
    client_order_id: str | None = None


@router.post("/broker/order")
async def broker_order(body: OrderRequest) -> dict[str, Any]:
    """Networked front door onto TradeTool — deliberately reuses the exact same
    OrderGuard checks (kill switch, mandate limits, artifact gate, market hours)
    as the LLM's submit_order tool, not a shortcut around them. Any caller that
    needs to place a live order (vinu-live's scheduler included) goes through
    this, not a direct AlpacaBroker.submit_order() call, so the safety layer
    can't be silently bypassed by a second code path.
    """
    tool = TradeTool()
    result_json = await asyncio.to_thread(tool.execute, **body.model_dump())
    return json.loads(result_json)


@router.get("/broker/asset/{symbol}")
async def broker_asset(symbol: str) -> dict[str, Any]:
    """Borrow check (16): shortable/easy_to_borrow for a symbol.

    Fail-open: broker not configured or lookup fails -> shortable None
    (caller allows, logs loudly). Only an explicit False blocks shorts.
    """
    try:
        broker = get_live_broker()
        data = await asyncio.to_thread(broker.get_asset, symbol)
        return {
            "symbol": symbol.upper(),
            "shortable": bool(data.get("shortable", False)),
            "easy_to_borrow": bool(data.get("easy_to_borrow", False)),
            "status": data.get("status", ""),
        }
    except Exception as e:
        return {"symbol": symbol.upper(), "shortable": None, "error": str(e)}


@router.get("/broker/performance/{artifact_id}")
async def broker_performance(artifact_id: str) -> dict[str, Any]:
    """Paper-trading daily returns for a BENCHING artifact.

    Called by ShadowEvaluator to compute paper Sharpe ratio. Returns the
    recorded daily returns list; an empty list means no data yet (evaluator
    returns ``insufficient_data``).
    """
    store = get_store()
    returns = store.get_daily_returns(artifact_id)
    return {"artifact_id": artifact_id, "daily_returns": returns}


class RecordPerformanceRequest(BaseModel):
    daily_returns: list[float]


@router.post("/broker/performance/{artifact_id}")
async def record_performance(artifact_id: str, body: RecordPerformanceRequest) -> dict[str, Any]:
    """Record paper-trading daily returns for an artifact.

    Called by vinu-live's cycle after each trading day to accumulate the
    per-artifact paper P&L history that ShadowEvaluator reads.
    """
    store = get_store()
    store.record_daily_returns(artifact_id, body.daily_returns)
    return {"status": "ok", "artifact_id": artifact_id, "n_returns": len(body.daily_returns)}
