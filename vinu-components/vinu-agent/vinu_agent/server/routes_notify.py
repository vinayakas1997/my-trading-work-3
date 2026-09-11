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


@router.post("/notify/trade-plan-pending")
async def notify_trade_plan_pending(body: TradePlanPendingRequest) -> dict[str, object]:
    """Best-effort fan-out to every configured channel -- one channel
    failing must not block the others, same posture as
    significance_triage.deliver_flag(). Never raises back to the caller
    (vinu-live's TradePlanApprovalWorker) -- a notification failure must
    never be treated as an approval failure, they're unrelated concerns."""
    config = load_config()

    # A33: noise control -- a plan that keeps failing the gate would
    # otherwise re-notify on every TradePlanApprovalWorker cycle. Keyed by
    # artifact so distinct plans never suppress each other. WARNING sev:
    # gets through quiet hours only if the operator lowered the bar.
    key = f"trade-plan-pending:{body.artifact_id}"
    gate = get_noise_gate()
    decision = gate.evaluate(key, Severity.WARNING)
    if not decision.send:
        LOG.info("Suppressing trade-plan-pending notice for %s: %s", body.artifact_id, decision.reason)
        return {"status": "suppressed", "reason": decision.reason, "delivered": 0}
    if not gate.reserve(key):
        LOG.info("trade-plan-pending notice for %s already in flight, skipping", body.artifact_id)
        return {"status": "in_flight", "delivered": 0}

    try:
        targets = build_channel_targets(config)
        if not targets:
            LOG.info("No notification channels configured, dropping trade-plan-pending notice for %s", body.artifact_id)
            return {"status": "no_channels_configured", "delivered": 0}

        text = _format_trade_plan_pending_message(body)
        delivered = 0
        for target in targets:
            channel_name = type(target.channel).__name__
            start = time.perf_counter()
            try:
                await target.channel.send_message(target.chat_id, text)
                delivered += 1
                NotificationDeliveryLog.record(
                    channel=channel_name, chat_id=target.chat_id, key=key,
                    severity=Severity.WARNING, ok=True,
                    latency_ms=(time.perf_counter() - start) * 1000,
                )
            except Exception as exc:
                LOG.exception(
                    "Failed to deliver trade-plan-pending notice for %s via a channel, continuing with the others",
                    body.artifact_id,
                )
                NotificationDeliveryLog.record(
                    channel=channel_name, chat_id=target.chat_id, key=key,
                    severity=Severity.WARNING, ok=False,
                    latency_ms=(time.perf_counter() - start) * 1000, error=str(exc),
                )
        if delivered:
            gate.record_sent(key)
        else:
            gate.release(key)
        return {"status": "ok", "delivered": delivered, "targets": len(targets)}
    finally:
        gate.release(key)
