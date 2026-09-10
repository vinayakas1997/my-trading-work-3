"""Stage 0 (G2b, research-discussion-v1/complete-plan/01-native-gaps.md):
/approve_plan (Telegram) and !approve_plan (Discord) force-approve a trade
plan the automated bootstrap gate rejected. Tests the HTTP call + reply
behavior directly against lightweight mock bot objects -- no real
python-telegram-bot Application / discord.py Client needed for this.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vinu_agent.channels.discord import DiscordChannel
from vinu_agent.channels.telegram import TelegramChannel


class MockResponse:
    def __init__(self, status_code: int, text: str = "") -> None:
        self.status_code = status_code
        self.text = text


def _telegram_channel(**config_overrides):
    config = {"token": "tok", "research_api_url": "http://test-research:8087", **config_overrides}
    return TelegramChannel(config, agent_service=MagicMock())


def _make_update(user_id: int = 123, username: str = "alice", args: list[str] | None = None):
    update = SimpleNamespace()
    update.effective_user = SimpleNamespace(id=user_id, username=username)
    update.message = MagicMock()
    update.message.reply_text = AsyncMock()
    context = SimpleNamespace(args=args or [])
    return update, context


class TestTelegramApprovePlan:
    @pytest.mark.asyncio
    async def test_approves_with_force_and_approver(self) -> None:
        channel = _telegram_channel()
        update, context = _make_update(args=["tp-1"])

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=MockResponse(200)) as post:
            await channel._cmd_approve_plan(update, context)

        assert post.await_args.args[0] == "http://test-research:8087/research/trade-plan/tp-1/approve"
        assert post.await_args.kwargs["params"] == {"force": "true", "approver": "telegram:123:alice"}
        update.message.reply_text.assert_awaited_once()
        assert "Approved tp-1" in update.message.reply_text.await_args.args[0]

    @pytest.mark.asyncio
    async def test_no_artifact_id_shows_usage(self) -> None:
        channel = _telegram_channel()
        update, context = _make_update(args=[])

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as post:
            await channel._cmd_approve_plan(update, context)

        post.assert_not_awaited()
        assert "Usage" in update.message.reply_text.await_args.args[0]

    @pytest.mark.asyncio
    async def test_disallowed_user_is_denied(self) -> None:
        channel = _telegram_channel(allowed_users=["999"])
        update, context = _make_update(user_id=123, args=["tp-1"])

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as post:
            await channel._cmd_approve_plan(update, context)

        post.assert_not_awaited()
        assert "Access denied" in update.message.reply_text.await_args.args[0]

    @pytest.mark.asyncio
    async def test_gate_rejection_surfaces_the_response_body(self) -> None:
        channel = _telegram_channel()
        update, context = _make_update(args=["tp-2"])

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=MockResponse(409, '{"reasons": ["already ACTIVE"]}')):
            await channel._cmd_approve_plan(update, context)

        reply = update.message.reply_text.await_args.args[0]
        assert "409" in reply
        assert "already ACTIVE" in reply

    @pytest.mark.asyncio
    async def test_connection_error_is_reported_not_raised(self) -> None:
        channel = _telegram_channel()
        update, context = _make_update(args=["tp-3"])

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, side_effect=ConnectionError("down")):
            await channel._cmd_approve_plan(update, context)  # must not raise

        assert "Error" in update.message.reply_text.await_args.args[0]


def _discord_channel(**config_overrides):
    config = {"token": "tok", "research_api_url": "http://test-research:8087", **config_overrides}
    return DiscordChannel(config, agent_service=MagicMock())


def _make_discord_message(content: str, user_id: int = 456, username: str = "bob"):
    message = MagicMock()
    message.content = content
    message.author = SimpleNamespace(id=user_id, name=username, bot=False)
    message.channel = MagicMock()
    message.channel.send = AsyncMock()
    return message


class TestDiscordApprovePlan:
    @pytest.mark.asyncio
    async def test_approves_with_force_and_approver(self) -> None:
        channel = _discord_channel()
        message = _make_discord_message("!approve_plan tp-1")

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=MockResponse(200)) as post:
            await channel._cmd_approve_plan(message, "456")

        assert post.await_args.args[0] == "http://test-research:8087/research/trade-plan/tp-1/approve"
        assert post.await_args.kwargs["params"] == {"force": "true", "approver": "discord:456:bob"}
        message.channel.send.assert_awaited_once()
        assert "Approved tp-1" in message.channel.send.await_args.args[0]

    @pytest.mark.asyncio
    async def test_no_artifact_id_shows_usage(self) -> None:
        channel = _discord_channel()
        message = _make_discord_message("!approve_plan")

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as post:
            await channel._cmd_approve_plan(message, "456")

        post.assert_not_awaited()
        assert "Usage" in message.channel.send.await_args.args[0]

    @pytest.mark.asyncio
    async def test_dispatched_from_handle_message(self) -> None:
        # Confirms !approve_plan is actually wired into _handle_message's
        # command dispatch, not just callable in isolation.
        channel = _discord_channel()
        message = _make_discord_message("!approve_plan tp-9")

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=MockResponse(200)):
            await channel._handle_message(message)

        message.channel.send.assert_awaited_once()
        assert "Approved tp-9" in message.channel.send.await_args.args[0]

    @pytest.mark.asyncio
    async def test_disallowed_user_never_reaches_approve_plan(self) -> None:
        channel = _discord_channel(allowed_users=["999"])
        message = _make_discord_message("!approve_plan tp-1", user_id=456)

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as post:
            await channel._handle_message(message)

        post.assert_not_awaited()
        assert "Access denied" in message.channel.send.await_args.args[0]
