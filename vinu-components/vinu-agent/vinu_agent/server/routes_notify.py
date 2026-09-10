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

from fastapi import APIRouter
from pydantic import BaseModel

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
    targets = build_channel_targets(config)
    if not targets:
        LOG.info("No notification channels configured, dropping trade-plan-pending notice for %s", body.artifact_id)
        return {"status": "no_channels_configured", "delivered": 0}

    text = _format_trade_plan_pending_message(body)
    delivered = 0
    for target in targets:
        try:
            await target.channel.send_message(target.chat_id, text)
            delivered += 1
        except Exception:
            LOG.exception(
                "Failed to deliver trade-plan-pending notice for %s via a channel, continuing with the others",
                body.artifact_id,
            )
    return {"status": "ok", "delivered": delivered, "targets": len(targets)}
