import asyncio
import logging
from typing import Any, Dict, Optional

import httpx
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
        # Stage 0 (G2b): /approve_plan posts directly to vinu-research's
        # approve endpoint -- deterministic HTTP call, not routed through
        # the LLM agent loop, same "don't let a safety-critical action
        # depend on free-text interpretation" posture as the rest of this
        # build (see the grounding-ledger discussion this plan is built on).
        self._research_api_url: str = config.get("research_api_url", "http://localhost:8087")
        # /rank (pull the screener's ranked list) and /track (push a picked
        # ticker's watchlist entry to vinu-news + vinu-stock-price,
        # synchronously) -- the deliberately-manual temporary bridge instead
        # of an automatic push pipeline (2026-09-11 design decision: keep a
        # human in the loop choosing which ranked symbol is worth pursuing,
        # rather than auto-feeding every entrant into vinu-research).
        services: Dict[str, str] = config.get("services", {})
        self._screener_api_url: str = services.get("vinu_screener", "http://localhost:8095")
        self._news_api_url: str = services.get("vinu_news", "http://localhost:8080")
        self._stock_api_url: str = services.get("vinu_stock_price", "http://localhost:8081")

    async def start(self) -> None:
        if not self._token:
            logger.error("Telegram token not configured")
            return

        builder = Application.builder().token(self._token)
        self._app = builder.build()

        self._app.add_handler(CommandHandler("start", self._cmd_start))
        self._app.add_handler(CommandHandler("new", self._cmd_new))
        self._app.add_handler(CommandHandler("approve_plan", self._cmd_approve_plan))
        self._app.add_handler(CommandHandler("rank", self._cmd_rank))
        self._app.add_handler(CommandHandler("track", self._cmd_track))
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
            "/rank <ranker_id> - Show the screener's latest ranked list\n"
            "/track <TICKER> - Add a ticker to vinu-news + vinu-stock-price watchlists\n"
            "Just send me a message to start researching."
        )

    async def _cmd_new(self, update: Update, context) -> None:
        user_id = str(update.effective_user.id) if update.effective_user else ""
        self._sessions.pop(user_id, None)
        await update.message.reply_text("Started a fresh session. What would you like to research?")

    async def _cmd_approve_plan(self, update: Update, context) -> None:
        """Stage 0 (G2b): force-approves a trade plan the automated
        bootstrap gate rejected. `approver` is the requesting Telegram
        user's id+username, logged with the override by vinu-research
        (approve_trade_plan's `force`/`approver` params) -- a forced
        approval is always distinguishable from a gate-cleared one, per
        the user's 2026-09-10 design decision for this feature."""
        user = update.effective_user
        user_id_int = user.id if user else 0
        user_id = str(user_id_int)
        if not self._is_allowed(user_id_int):
            await update.message.reply_text("Access denied.")
            return

        args = context.args if context and getattr(context, "args", None) else []
        if not args:
            await update.message.reply_text("Usage: /approve_plan <artifact_id>")
            return
        artifact_id = args[0]
        approver = f"telegram:{user_id}:{user.username or ''}" if user else "telegram:unknown"

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{self._research_api_url}/research/trade-plan/{artifact_id}/approve",
                    params={"force": "true", "approver": approver},
                )
            if resp.status_code == 200:
                await update.message.reply_text(f"Approved {artifact_id} (forced by {approver}).")
            elif resp.status_code == 404:
                await update.message.reply_text(f"No trade plan found with id {artifact_id}.")
            else:
                detail = resp.text
                await update.message.reply_text(f"Approval failed (HTTP {resp.status_code}): {detail}")
        except Exception as exc:
            logger.error("Error forcing approval of %s: %s", artifact_id, exc)
            await update.message.reply_text(f"Error contacting research service: {exc}")

    def _auth_headers(self) -> Optional[dict]:
        try:
            from vinu_infra.auth import internal_auth_headers
            return internal_auth_headers() or None
        except Exception:
            return None

    def _format_ranked_list(self, ranker_id: str, snapshot: dict) -> str:
        top = snapshot.get("top", [])
        if not top:
            return f"Ranker '{ranker_id}' has no candidates in its latest run."
        lines = [f"Ranked list for '{ranker_id}' (generated_at={snapshot.get('generated_at')}):"]
        for i, c in enumerate(top, start=1):
            fields = c.get("fields", {}) or {}
            # price/volume are always present (rankers/runner.py always carries
            # them); anything else (rsi, momentum, ...) is whatever FactorSpecs
            # this ranker was configured with -- print whatever's there rather
            # than hardcoding indicator names the ranker may not even compute.
            detail = ", ".join(f"{k}={v:.2f}" for k, v in fields.items())
            lines.append(f"{i}. {c['symbol']}  score={c.get('final_score', 0):.3f}" + (f"  ({detail})" if detail else ""))
        return "\n".join(lines)

    async def _cmd_rank(self, update: Update, context) -> None:
        user_id = update.effective_user.id if update.effective_user else 0
        if not self._is_allowed(user_id):
            await update.message.reply_text("Access denied.")
            return
        args = context.args if context and getattr(context, "args", None) else []
        if not args:
            await update.message.reply_text("Usage: /rank <ranker_id>")
            return
        ranker_id = args[0]
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{self._screener_api_url}/screener/rankers/{ranker_id}/latest",
                    headers=self._auth_headers(),
                )
            if resp.status_code == 404:
                await update.message.reply_text(f"No ranked list yet for '{ranker_id}' (never run, or unknown ranker id).")
                return
            resp.raise_for_status()
            await update.message.reply_text(self._format_ranked_list(ranker_id, resp.json()))
        except Exception as exc:
            logger.error("Error fetching ranked list for %s: %s", ranker_id, exc)
            await update.message.reply_text(f"Error contacting screener service: {exc}")

    async def _cmd_track(self, update: Update, context) -> None:
        """Manual, deliberately synchronous bridge: pushes one ticker onto
        both vinu-news and vinu-stock-price's watchlists (each an independent
        service with its own watchlist -- see config.services docstring),
        waiting for both and reporting both outcomes rather than firing one
        and hoping. No rollback on partial failure -- a watchlist add is
        cheap to retry, not worth atomicity machinery for."""
        user_id = update.effective_user.id if update.effective_user else 0
        if not self._is_allowed(user_id):
            await update.message.reply_text("Access denied.")
            return
        args = context.args if context and getattr(context, "args", None) else []
        if not args:
            await update.message.reply_text("Usage: /track <TICKER>")
            return
        ticker = args[0].strip().upper()
        headers = self._auth_headers()
        body = {"tickers": [ticker]}

        async def _add(name: str, base_url: str) -> str:
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.post(f"{base_url}/watchlist/tickers", json=body, headers=headers)
                if resp.status_code == 200:
                    return f"{name}"
                return f"{name} (HTTP {resp.status_code}: {resp.text})"
            except Exception as exc:
                return f"{name} (error: {exc})"

        news_result, stock_result = await asyncio.gather(
            _add("vinu-news", f"{self._news_api_url}/news"),
            _add("vinu-stock-price", f"{self._stock_api_url}/stock"),
        )
        await update.message.reply_text(f"Tracking {ticker}:\n- {news_result}\n- {stock_result}")

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
