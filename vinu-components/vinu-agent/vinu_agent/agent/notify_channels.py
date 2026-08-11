"""One-shot outbound delivery channels for Significance Triage (Phase 9
scheduler-wiring, New-talk-agents/new-thinking/new-restructure/phases/
phase-9-scheduler-wiring/). Deliberately NOT `channels/discord.py` /
`channels/telegram.py` -- those implement the interactive receive-and-
reply bot, which requires a persistent connection via `.start()`
(`Application.builder()...build()` / `discord.Client(...)`) before
`send_message()` does anything (both silently no-op otherwise, confirmed
by reading them directly). A scheduler worker firing an occasional
unprompted flag has no reason to hold that connection open. Both classes
here implement `significance_triage.py`'s own `Channel` protocol
(`async def send_message(self, chat_id: str, text: str) -> None`) via a
single outbound REST call instead -- no gateway/websocket, no bot startup.
"""

from __future__ import annotations

import logging

import httpx

LOG = logging.getLogger(__name__)

TELEGRAM_MAX_LEN = 4000
DISCORD_MAX_LEN = 2000


class HttpTelegramChannel:
    """Telegram Bot API's plain `sendMessage` endpoint -- no polling
    connection needed for a one-shot outbound message."""

    def __init__(self, token: str, *, timeout: float = 15.0) -> None:
        self._token = token
        self._timeout = timeout

    async def send_message(self, chat_id: str, text: str) -> None:
        if not self._token:
            LOG.warning("Telegram token not configured, dropping message")
            return
        url = f"https://api.telegram.org/bot{self._token}/sendMessage"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            for i in range(0, len(text), TELEGRAM_MAX_LEN):
                chunk = text[i:i + TELEGRAM_MAX_LEN]
                resp = await client.post(url, json={"chat_id": chat_id, "text": chunk})
                if resp.status_code != 200:
                    LOG.error("Telegram send to %s failed: HTTP %d %s", chat_id, resp.status_code, resp.text)


class HttpDiscordChannel:
    """Discord's REST API (`POST /channels/{id}/messages`, bot-token
    authenticated) -- no gateway connection needed for a one-shot outbound
    message. The bot must already be a member of the target guild with
    permission to post in the channel."""

    def __init__(self, token: str, *, timeout: float = 15.0) -> None:
        self._token = token
        self._timeout = timeout

    async def send_message(self, chat_id: str, text: str) -> None:
        if not self._token:
            LOG.warning("Discord token not configured, dropping message")
            return
        url = f"https://discord.com/api/v10/channels/{chat_id}/messages"
        headers = {"Authorization": f"Bot {self._token}"}
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            for i in range(0, len(text), DISCORD_MAX_LEN):
                chunk = text[i:i + DISCORD_MAX_LEN]
                resp = await client.post(url, headers=headers, json={"content": chunk})
                if resp.status_code not in (200, 201):
                    LOG.error("Discord send to %s failed: HTTP %d %s", chat_id, resp.status_code, resp.text)
