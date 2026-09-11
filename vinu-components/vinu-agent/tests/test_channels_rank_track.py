"""/rank (pull the screener's latest ranked list) and /track (push a ticker
onto vinu-news + vinu-stock-price watchlists synchronously) -- the manual
Telegram bridge, 2026-09-11 design decision. Same lightweight mock-bot
testing style as test_channels_approve_plan.py, no real python-telegram-bot
Application needed.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vinu_agent.channels.telegram import TelegramChannel


class MockResponse:
    def __init__(self, status_code: int, json_body: dict | None = None, text: str = "") -> None:
        self.status_code = status_code
        self._json = json_body or {}
        self.text = text or str(json_body or "")

    def json(self) -> dict:
        return self._json

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def _telegram_channel(**config_overrides):
    config = {
        "token": "tok",
        "services": {
            "vinu_screener": "http://test-screener:8095",
            "vinu_news": "http://test-news:8080",
            "vinu_stock_price": "http://test-stock:8081",
        },
        **config_overrides,
    }
    return TelegramChannel(config, agent_service=MagicMock())


def _make_update(user_id: int = 123, args: list[str] | None = None):
    update = SimpleNamespace()
    update.effective_user = SimpleNamespace(id=user_id, username="alice")
    update.message = MagicMock()
    update.message.reply_text = AsyncMock()
    context = SimpleNamespace(args=args or [])
    return update, context


class TestRank:
    @pytest.mark.asyncio
    async def test_shows_ranked_list_with_fields(self) -> None:
        channel = _telegram_channel()
        update, context = _make_update(args=["daily"])
        snapshot = {
            "generated_at": 100.0,
            "top": [
                {"symbol": "AAPL", "final_score": 1.234, "fields": {"price": 190.5, "rsi": 28.4}},
                {"symbol": "MSFT", "final_score": 0.987, "fields": {"price": 410.0, "rsi": 55.1}},
            ],
        }
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=MockResponse(200, snapshot)) as get:
            await channel._cmd_rank(update, context)

        assert get.await_args.args[0] == "http://test-screener:8095/screener/rankers/daily/latest"
        reply = update.message.reply_text.await_args.args[0]
        assert "1. AAPL" in reply
        assert "rsi=28.40" in reply
        assert "2. MSFT" in reply

    @pytest.mark.asyncio
    async def test_no_ranker_id_shows_usage(self) -> None:
        channel = _telegram_channel()
        update, context = _make_update(args=[])

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as get:
            await channel._cmd_rank(update, context)

        get.assert_not_awaited()
        assert "Usage" in update.message.reply_text.await_args.args[0]

    @pytest.mark.asyncio
    async def test_unknown_ranker_404_is_reported_not_raised(self) -> None:
        channel = _telegram_channel()
        update, context = _make_update(args=["ghost"])

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=MockResponse(404)):
            await channel._cmd_rank(update, context)

        assert "No ranked list yet" in update.message.reply_text.await_args.args[0]

    @pytest.mark.asyncio
    async def test_disallowed_user_is_denied(self) -> None:
        channel = _telegram_channel(allowed_users=["999"])
        update, context = _make_update(user_id=123, args=["daily"])

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as get:
            await channel._cmd_rank(update, context)

        get.assert_not_awaited()
        assert "Access denied" in update.message.reply_text.await_args.args[0]

    @pytest.mark.asyncio
    async def test_connection_error_is_reported_not_raised(self) -> None:
        channel = _telegram_channel()
        update, context = _make_update(args=["daily"])

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=ConnectionError("down")):
            await channel._cmd_rank(update, context)  # must not raise

        assert "Error" in update.message.reply_text.await_args.args[0]


class TestTrack:
    @pytest.mark.asyncio
    async def test_adds_to_both_services(self) -> None:
        channel = _telegram_channel()
        update, context = _make_update(args=["aapl"])

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=MockResponse(200)) as post:
            await channel._cmd_track(update, context)

        urls = {call.args[0] for call in post.await_args_list}
        assert urls == {
            "http://test-news:8080/news/watchlist/tickers",
            "http://test-stock:8081/stock/watchlist/tickers",
        }
        for call in post.await_args_list:
            assert call.kwargs["json"] == {"tickers": ["AAPL"]}
        reply = update.message.reply_text.await_args.args[0]
        assert "Tracking AAPL" in reply
        assert "vinu-news" in reply
        assert "vinu-stock-price" in reply

    @pytest.mark.asyncio
    async def test_uppercases_the_ticker(self) -> None:
        channel = _telegram_channel()
        update, context = _make_update(args=["tsla"])

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=MockResponse(200)) as post:
            await channel._cmd_track(update, context)

        assert all(call.kwargs["json"] == {"tickers": ["TSLA"]} for call in post.await_args_list)

    @pytest.mark.asyncio
    async def test_one_service_failing_does_not_block_the_other(self) -> None:
        channel = _telegram_channel()
        update, context = _make_update(args=["aapl"])

        async def _side_effect(url, *args, **kwargs):
            if "news" in url:
                raise ConnectionError("news is down")
            return MockResponse(200)

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, side_effect=_side_effect):
            await channel._cmd_track(update, context)  # must not raise

        reply = update.message.reply_text.await_args.args[0]
        assert "vinu-news (error: news is down)" in reply
        assert "vinu-stock-price\n" in reply or reply.endswith("vinu-stock-price")

    @pytest.mark.asyncio
    async def test_no_ticker_shows_usage(self) -> None:
        channel = _telegram_channel()
        update, context = _make_update(args=[])

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as post:
            await channel._cmd_track(update, context)

        post.assert_not_awaited()
        assert "Usage" in update.message.reply_text.await_args.args[0]

    @pytest.mark.asyncio
    async def test_disallowed_user_is_denied(self) -> None:
        channel = _telegram_channel(allowed_users=["999"])
        update, context = _make_update(user_id=123, args=["aapl"])

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as post:
            await channel._cmd_track(update, context)

        post.assert_not_awaited()
        assert "Access denied" in update.message.reply_text.await_args.args[0]
