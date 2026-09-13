"""Networked front door for pushing a chat notification -- Stage 0 (G2b,
research-discussion-v1/complete-plan/01-native-gaps.md). Other vinu-*
services (vinu-live's TradePlanApprovalWorker, so far) have no direct
access to the Telegram/Discord bot tokens or the interactive bot
processes running inside this container's AgentService -- this is the one
HTTP endpoint they go through to reach a configured channel, same
"networked front door, not a second code path" idiom as routes_broker.py's
own docstring establishes for the kill switch.

Deliberately reuses agent/scheduler_workers.py's already-built
`build_channel_targets()` (each channel independently gated on its own
token+admin-id being configured) and notify_channels.py's one-shot HTTP
senders (`HttpTelegramChannel`/`HttpDiscordChannel`) -- no gateway
connection needed for an occasional outbound push, same reasoning
notify_channels.py's own docstring gives for not reusing the interactive
`channels/telegram.py`/`channels/discord.py` bot classes here.
"""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter
from pydantic import BaseModel

from ..agent.notification_noise import (
    NotificationDeliveryLog,
    Severity,
    get_noise_gate,
)
from ..agent.scheduler_workers import build_channel_targets
from ..config import load_config

router = APIRouter()

LOG = logging.getLogger(__name__)


class TradePlanPendingRequest(BaseModel):
    artifact_id: str
    symbol: str
    reasons: list[str] = []


def _format_trade_plan_pending_message(body: TradePlanPendingRequest) -> str:
    reasons_text = "; ".join(body.reasons) if body.reasons else "gate rejected"
    return (
        f"[Trade Plan Pending Approval] {body.symbol} ({body.artifact_id})\n"
        f"Rejected: {reasons_text}\n"
        f"Reply /approve_plan {body.artifact_id} to force-approve (your identity is logged)."
    )


async def _deliver_notification(key: str, severity: Severity, text: str) -> dict[str, object]:
    """Shared fan-out body for every /notify/* route below -- noise-gated,
    best-effort per channel (one channel failing must not block the others,
    same posture as significance_triage.deliver_flag()), and never raises
    back to the caller: a notification failure must never be treated as a
    failure of whatever real thing it was reporting on."""
    config = load_config()
    gate = get_noise_gate()
    decision = gate.evaluate(key, severity)
    if not decision.send:
        LOG.info("Suppressing notice for %s: %s", key, decision.reason)
        return {"status": "suppressed", "reason": decision.reason, "delivered": 0}
    if not gate.reserve(key):
        LOG.info("Notice for %s already in flight, skipping", key)
        return {"status": "in_flight", "delivered": 0}

    try:
        targets = build_channel_targets(config)
        if not targets:
            LOG.info("No notification channels configured, dropping notice for %s", key)
            return {"status": "no_channels_configured", "delivered": 0}

        delivered = 0
        for target in targets:
            channel_name = type(target.channel).__name__
            start = time.perf_counter()
            try:
                await target.channel.send_message(target.chat_id, text)
                delivered += 1
                NotificationDeliveryLog.record(
                    channel=channel_name, chat_id=target.chat_id, key=key,
                    severity=severity, ok=True,
                    latency_ms=(time.perf_counter() - start) * 1000,
                )
            except Exception as exc:
                LOG.exception(
                    "Failed to deliver notice for %s via a channel, continuing with the others", key,
                )
                NotificationDeliveryLog.record(
                    channel=channel_name, chat_id=target.chat_id, key=key,
                    severity=severity, ok=False,
                    latency_ms=(time.perf_counter() - start) * 1000, error=str(exc),
                )
        if delivered:
            gate.record_sent(key)
        else:
            gate.release(key)
        return {"status": "ok", "delivered": delivered, "targets": len(targets)}
    finally:
        gate.release(key)


@router.post("/notify/trade-plan-pending")
async def notify_trade_plan_pending(body: TradePlanPendingRequest) -> dict[str, object]:
    """Best-effort fan-out to every configured channel. Never raises back to
    the caller (vinu-live's TradePlanApprovalWorker) -- a notification
    failure must never be treated as an approval failure, they're unrelated
    concerns."""
    # A33: noise control -- a plan that keeps failing the gate would
    # otherwise re-notify on every TradePlanApprovalWorker cycle. Keyed by
    # artifact so distinct plans never suppress each other. WARNING sev:
    # gets through quiet hours only if the operator lowered the bar.
    key = f"trade-plan-pending:{body.artifact_id}"
    text = _format_trade_plan_pending_message(body)
    return await _deliver_notification(key, Severity.WARNING, text)


class ReconciliationDriftRequest(BaseModel):
    """A book/broker discrepancy that TradePlanOrchestrator._reconcile_symbol
    deliberately does NOT auto-correct (a phantom broker position could
    belong to another strategy or a manual trade; a side conflict is never
    safe to auto-flip) -- see orchestrator.py's own reasoning. Auto-trading
    on either case would be actively harmful if the guess is wrong, so this
    stays a human-review alert, not a healing action. What was missing
    before this route existed was any way for that alert to reach further
    than a server log nobody was necessarily tailing."""

    symbol: str
    action: str  # "alert_phantom_broker_position" | "alert_side_conflict"
    book_qty: float | None = None
    broker_qty: float | None = None


def _format_reconciliation_drift_message(body: ReconciliationDriftRequest) -> str:
    if body.action == "alert_phantom_broker_position":
        detail = (
            f"broker holds {body.broker_qty} but the book has no position for it. "
            f"Could be another strategy, a manual trade, or a bug -- NOT auto-corrected."
        )
    elif body.action == "alert_side_conflict":
        detail = (
            f"book and broker disagree on side (book={body.book_qty}, broker={body.broker_qty}) "
            f"-- NOT auto-corrected, never auto-flipped."
        )
    else:
        detail = f"{body.action} (book={body.book_qty}, broker={body.broker_qty})"
    return f"[Reconciliation Drift] {body.symbol}: {detail}\nNeeds manual review."


@router.post("/notify/reconciliation-drift")
async def notify_reconciliation_drift(body: ReconciliationDriftRequest) -> dict[str, object]:
    """Same 'networked front door' idiom as notify_trade_plan_pending --
    vinu-live's TradePlanOrchestrator has no direct channel access. CRITICAL
    severity: an unmanaged live position or a book/broker discrepancy is a
    real money-risk condition, not routine noise. Deduped per (symbol,
    action) so a condition that persists across cycles doesn't re-notify
    every cycle -- see _reconcile_book_with_broker, which calls this once
    per cycle for as long as the condition is still detected."""
    key = f"reconciliation-drift:{body.symbol}:{body.action}"
    text = _format_reconciliation_drift_message(body)
    return await _deliver_notification(key, Severity.CRITICAL, text)
