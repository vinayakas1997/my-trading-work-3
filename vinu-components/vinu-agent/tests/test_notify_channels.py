"""Tests for the one-shot outbound delivery channels -- Phase 9
scheduler-wiring (New-talk-agents/new-thinking/new-restructure/phases/
phase-9-scheduler-wiring/). See agent/notify_channels.py.
"""

from __future__ import annotations

import asyncio

from vinu_agent.agent.notify_channels import (
    DISCORD_MAX_LEN,
    TELEGRAM_MAX_LEN,
    HttpDiscordChannel,
    HttpTelegramChannel,
)


class _FakeResponse:
    def __init__(self, status_code: int = 200, text: str = "") -> None:
        self.status_code = status_code
        self.text = text


def _fake_async_client(post_impl):
    class Client:
        def __init__(self, *a, **kw) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, **kwargs):
            return post_impl(url, **kwargs)

    return Client


class TestHttpTelegramChannel:
    def test_posts_to_telegram_send_message_endpoint(self, monkeypatch) -> None:
        captured = {}

        def post_impl(url, **kwargs):
            captured["url"] = url
            captured["json"] = kwargs.get("json")
            return _FakeResponse()

        monkeypatch.setattr("vinu_agent.agent.notify_channels.httpx.AsyncClient", _fake_async_client(post_impl))

        channel = HttpTelegramChannel("tok123")
        asyncio.run(channel.send_message("chat1", "hello"))

        assert captured["url"] == "https://api.telegram.org/bottok123/sendMessage"
        assert captured["json"] == {"chat_id": "chat1", "text": "hello"}

    def test_no_token_does_not_call_out(self, monkeypatch) -> None:
        calls = []

        def post_impl(url, **kwargs):
            calls.append(url)
            return _FakeResponse()

        monkeypatch.setattr("vinu_agent.agent.notify_channels.httpx.AsyncClient", _fake_async_client(post_impl))

        channel = HttpTelegramChannel("")
        asyncio.run(channel.send_message("chat1", "hello"))

        assert calls == []

    def test_long_message_is_chunked(self, monkeypatch) -> None:
        posts = []

        def post_impl(url, **kwargs):
            posts.append(kwargs["json"]["text"])
            return _FakeResponse()

        monkeypatch.setattr("vinu_agent.agent.notify_channels.httpx.AsyncClient", _fake_async_client(post_impl))

        text = "x" * (TELEGRAM_MAX_LEN + 500)
        channel = HttpTelegramChannel("tok")
        asyncio.run(channel.send_message("chat1", text))

        assert len(posts) == 2
        assert len(posts[0]) == TELEGRAM_MAX_LEN
        assert len(posts[1]) == 500


class TestHttpDiscordChannel:
    def test_posts_to_discord_channel_messages_endpoint_with_bot_auth(self, monkeypatch) -> None:
        captured = {}

        def post_impl(url, **kwargs):
            captured["url"] = url
            captured["headers"] = kwargs.get("headers")
            captured["json"] = kwargs.get("json")
            return _FakeResponse(201)

        monkeypatch.setattr("vinu_agent.agent.notify_channels.httpx.AsyncClient", _fake_async_client(post_impl))

        channel = HttpDiscordChannel("tok456")
        asyncio.run(channel.send_message("999", "hello discord"))

        assert captured["url"] == "https://discord.com/api/v10/channels/999/messages"
        assert captured["headers"] == {"Authorization": "Bot tok456"}
        assert captured["json"] == {"content": "hello discord"}

    def test_no_token_does_not_call_out(self, monkeypatch) -> None:
        calls = []

        def post_impl(url, **kwargs):
            calls.append(url)
            return _FakeResponse()

        monkeypatch.setattr("vinu_agent.agent.notify_channels.httpx.AsyncClient", _fake_async_client(post_impl))

        channel = HttpDiscordChannel("")
        asyncio.run(channel.send_message("999", "hello"))

        assert calls == []

    def test_long_message_is_chunked(self, monkeypatch) -> None:
        posts = []

        def post_impl(url, **kwargs):
            posts.append(kwargs["json"]["content"])
            return _FakeResponse(201)

        monkeypatch.setattr("vinu_agent.agent.notify_channels.httpx.AsyncClient", _fake_async_client(post_impl))

        text = "y" * (DISCORD_MAX_LEN + 100)
        channel = HttpDiscordChannel("tok")
        asyncio.run(channel.send_message("999", text))

        assert len(posts) == 2
        assert len(posts[0]) == DISCORD_MAX_LEN
        assert len(posts[1]) == 100
