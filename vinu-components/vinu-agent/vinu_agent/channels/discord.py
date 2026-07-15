import asyncio
import logging
from typing import Any, Dict, Optional

import discord
from discord import Intents

from ..service import AgentService
from .base import BaseChannel

logger = logging.getLogger(__name__)

DISCORD_MAX_LEN = 2000


class DiscordChannel(BaseChannel):
    name = "discord"

    def __init__(self, config: Dict[str, Any], agent_service: AgentService) -> None:
        super().__init__(config)
        self._agent_service = agent_service
        self._token: str = config.get("token", "")
        self._allowed_users: list = config.get("allowed_users", ["*"])
        self._client: Optional[discord.Client] = None
        self._sessions: Dict[str, str] = {}

    async def start(self) -> None:
        if not self._token:
            logger.error("Discord token not configured")
            return

        intents = Intents.default()
        intents.message_content = True

        self._client = discord.Client(intents=intents)

        @self._client.event
        async def on_ready() -> None:
            logger.info("Discord channel started as %s", self._client.user)

        @self._client.event
        async def on_message(message: discord.Message) -> None:
            if message.author.bot:
                return
            await self._handle_message(message)

        self._running = True
        asyncio.create_task(self._client.start(self._token))

        idle = self.config.get("idle", True)
        if idle:
            while self._running:
                await asyncio.sleep(1)

    async def stop(self) -> None:
        self._running = False
        if self._client and self._client.is_ready():
            await self._client.close()

    async def send_message(self, chat_id: str, text: str) -> None:
        if not self._client or not self._client.is_ready():
            return
        channel = self._client.get_channel(int(chat_id))
        if not channel:
            logger.error("Channel %s not found", chat_id)
            return
        for i in range(0, len(text), DISCORD_MAX_LEN):
            chunk = text[i:i + DISCORD_MAX_LEN]
            try:
                await channel.send(chunk)
            except Exception as exc:
                logger.error("Failed to send to %s: %s", chat_id, exc)

    def _is_allowed(self, user_id: int) -> bool:
        if "*" in self._allowed_users:
            return True
        return str(user_id) in self._allowed_users

    async def _handle_message(self, message: discord.Message) -> None:
        user_id = str(message.author.id)
        chat_id = str(message.channel.id)
        text = message.content

        if not self._is_allowed(message.author.id):
            await message.channel.send("Access denied.")
            return

        if not text.strip():
            return

        if text.startswith("!start"):
            await message.channel.send(
                "Welcome to Vinu-Agent. I am your quantitative trading research assistant.\n\n"
                "Commands:\n"
                "`!new` - Start a new conversation\n"
                "Just send me a message to start researching."
            )
            return

        if text.startswith("!new"):
            self._sessions.pop(user_id, None)
            await message.channel.send("Started a fresh session. What would you like to research?")
            return

        async with message.channel.typing():
            try:
                session_id = self._sessions.get(user_id)
                if not session_id:
                    session = await self._agent_service.create_session(title=f"Discord-{user_id}")
                    session_id = session.session_id
                    self._sessions[user_id] = session_id

                result = await self._agent_service.send_message(session_id, text)
                reply = result.get("content", "No response generated.")
                await self.send_message(chat_id, reply)

            except Exception as exc:
                logger.error("Error handling message: %s", exc)
                await message.channel.send(f"Error: {exc}")
