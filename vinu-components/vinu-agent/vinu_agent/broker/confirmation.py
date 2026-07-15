"""Async opt-in confirmation flow for trade proposals via Telegram/Discord."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

CONFIRMATION_TIMEOUT = 300


class ConfirmationTimeout(Exception):
    ...


class ConfirmationDenied(Exception):
    ...


@dataclass
class TradeProposal:
    symbol: str
    side: str
    qty: float
    order_type: str
    limit_price: float | None = None
    stop_price: float | None = None
    estimated_value: float = 0.0

    def to_message(self) -> str:
        lines = [
            "**Trade Proposal**",
            f"Symbol: {self.symbol}",
            f"Side: {self.side.upper()}",
            f"Qty: {self.qty}",
            f"Type: {self.order_type}",
        ]
        if self.limit_price:
            lines.append(f"Limit: ${self.limit_price:.2f}")
        if self.stop_price:
            lines.append(f"Stop: ${self.stop_price:.2f}")
        lines.append(f"Estimated Value: ${self.estimated_value:.2f}")
        lines.append("")
        lines.append("Reply with `approve` to confirm, `deny` to reject.")
        return "\n".join(lines)


class ConfirmationHandler:
    def __init__(self, channels: list[Any] | None = None) -> None:
        self._channels: list[Any] = channels or []
        self._pending: dict[str, asyncio.Event] = {}
        self._responses: dict[str, str] = {}

    async def request_confirmation(
        self,
        proposal: TradeProposal,
        chat_ids: list[str] | None = None,
        timeout: int = CONFIRMATION_TIMEOUT,
    ) -> str:
        confirmation_id = f"{proposal.symbol}_{proposal.side}_{id(proposal)}"
        event = asyncio.Event()
        self._pending[confirmation_id] = event

        message = proposal.to_message()
        for channel in self._channels:
            for chat_id in (chat_ids or []):
                try:
                    await channel.send_message(chat_id, message)
                except Exception as exc:
                    logger.error("Failed to send confirmation to %s: %s", chat_id, exc)

        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            self._pending.pop(confirmation_id, None)
            raise ConfirmationTimeout("User did not respond in time")

        self._pending.pop(confirmation_id, None)
        response = self._responses.pop(confirmation_id, "")
        if response.lower() in ("deny", "reject", "no", "cancel"):
            raise ConfirmationDenied(f"User denied trade: {response}")
        if response.lower() in ("approve", "confirm", "yes"):
            return response

        raise ConfirmationDenied(f"Unexpected response: {response}")

    def resolve_confirmation(self, confirmation_id: str, response: str) -> None:
        self._responses[confirmation_id] = response
        event = self._pending.get(confirmation_id)
        if event:
            event.set()
