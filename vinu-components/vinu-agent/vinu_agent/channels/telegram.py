import asyncio
import logging
from typing import Any, Dict, Optional

from telegram import BotCommand, Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from ..service import AgentService
from .base import BaseChannel

logger = logging.getLogger(__name__)

TELEGRAM_MAX_LEN = 4000


class TelegramChannel(BaseChannel):
    name = "telegram"

    def __init__(self, config: Dict[str, Any], agent_service: AgentService) -> None:
        super().__init__(config)
        self._agent_service = agent_service
        self._token: str = config.get("token", "")
        self._allowed_users: list = config.get("allowed_users", ["*"])
        self._app: Optional[Application] = None
        self._sessions: Dict[str, str] = {}

    async def start(self) -> None:
        if not self._token:
            logger.error("Telegram token not configured")
            return

        builder = Application.builder().token(self._token)
        self._app = builder.build()

        self._app.add_handler(CommandHandler("start", self._cmd_start))
        self._app.add_handler(CommandHandler("new", self._cmd_new))
        self._app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message))

        await self._app.initialize()
        await self._app.start()
        self._running = True
        logger.info("Telegram channel started")

        idle = self.config.get("idle", True)
        if idle:
            while self._running:
                await asyncio.sleep(1)

    async def stop(self) -> None:
        self._running = False
        if self._app:
            await self._app.stop()
            await self._app.shutdown()

    async def send_message(self, chat_id: str, text: str) -> None:
        if not self._app:
            return
        for i in range(0, len(text), TELEGRAM_MAX_LEN):
            chunk = text[i:i + TELEGRAM_MAX_LEN]
            try:
                await self._app.bot.send_message(chat_id=chat_id, text=chunk)
            except Exception as exc:
                logger.error("Failed to send to %s: %s", chat_id, exc)

    def _is_allowed(self, user_id: int) -> bool:
        if "*" in self._allowed_users:
            return True
        return str(user_id) in self._allowed_users

    async def _cmd_start(self, update: Update, context) -> None:
        user_id = update.effective_user.id if update.effective_user else 0
        if not self._is_allowed(user_id):
            await update.message.reply_text("Access denied.")
            return
        await update.message.reply_text(
            "Welcome to Vinu-Agent. I am your quantitative trading research assistant.\n\n"
            "Commands:\n"
            "/new - Start a new conversation\n"
            "Just send me a message to start researching."
        )

    async def _cmd_new(self, update: Update, context) -> None:
        user_id = str(update.effective_user.id) if update.effective_user else ""
        self._sessions.pop(user_id, None)
        await update.message.reply_text("Started a fresh session. What would you like to research?")

    async def _handle_message(self, update: Update, context) -> None:
        user_id = str(update.effective_user.id) if update.effective_user else ""
        chat_id = str(update.effective_chat.id) if update.effective_chat else ""
        text = update.message.text if update.message else ""

        if not self._is_allowed(int(user_id)):
            await update.message.reply_text("Access denied.")
            return

        if not text.strip():
            return

        await update.message.chat.send_action(action="typing")

        try:
            session_id = self._sessions.get(user_id)
            if not session_id:
                session = await self._agent_service.create_session(title=f"Telegram-{user_id}")
                session_id = session.session_id
                self._sessions[user_id] = session_id

            result = await self._agent_service.send_message(session_id, text)
            reply = result.get("content", "No response generated.")
            await self.send_message(chat_id, reply)

        except Exception as exc:
            logger.error("Error handling message: %s", exc)
            await update.message.reply_text(f"Error: {exc}")
