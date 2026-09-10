from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from vinu_agent.config import AgentConfig
from vinu_agent.server.routes_notify import router


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def _body(artifact_id="tp-1", symbol="AAPL", reasons=None):
    return {"artifact_id": artifact_id, "symbol": symbol, "reasons": reasons or ["no ACTIVE strategy for AAPL"]}


def test_no_channels_configured_reports_zero_delivered(client) -> None:
    with patch("vinu_agent.server.routes_notify.load_config", return_value=AgentConfig()):
        resp = client.post("/notify/trade-plan-pending", json=_body())

    assert resp.status_code == 200
    assert resp.json() == {"status": "no_channels_configured", "delivered": 0}


def test_delivers_to_all_configured_channels(client) -> None:
    config = AgentConfig(
        telegram_token="tok", telegram_admin_chat_id="chat1",
        discord_token="dtok", discord_admin_channel_id="999",
    )
    with patch("vinu_agent.server.routes_notify.load_config", return_value=config):
        with patch("vinu_agent.agent.notify_channels.HttpTelegramChannel.send_message", new_callable=AsyncMock) as tg_send, \
             patch("vinu_agent.agent.notify_channels.HttpDiscordChannel.send_message", new_callable=AsyncMock) as dc_send:
            resp = client.post("/notify/trade-plan-pending", json=_body())

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["delivered"] == 2
    tg_send.assert_awaited_once()
    dc_send.assert_awaited_once()
    # Message content includes the artifact_id and the force-approve instruction.
    sent_text = tg_send.await_args.args[1]
    assert "tp-1" in sent_text
    assert "/approve_plan tp-1" in sent_text
    assert "no ACTIVE strategy for AAPL" in sent_text


def test_one_channel_failing_does_not_block_the_other(client) -> None:
    config = AgentConfig(
        telegram_token="tok", telegram_admin_chat_id="chat1",
        discord_token="dtok", discord_admin_channel_id="999",
    )
    with patch("vinu_agent.server.routes_notify.load_config", return_value=config):
        with patch("vinu_agent.agent.notify_channels.HttpTelegramChannel.send_message", new_callable=AsyncMock, side_effect=ConnectionError("down")), \
             patch("vinu_agent.agent.notify_channels.HttpDiscordChannel.send_message", new_callable=AsyncMock) as dc_send:
            resp = client.post("/notify/trade-plan-pending", json=_body())

    assert resp.status_code == 200
    body = resp.json()
    assert body["delivered"] == 1  # only Discord succeeded
    dc_send.assert_awaited_once()


def test_never_raises_back_to_caller_on_total_delivery_failure(client) -> None:
    config = AgentConfig(telegram_token="tok", telegram_admin_chat_id="chat1")
    with patch("vinu_agent.server.routes_notify.load_config", return_value=config):
        with patch("vinu_agent.agent.notify_channels.HttpTelegramChannel.send_message", new_callable=AsyncMock, side_effect=Exception("boom")):
            resp = client.post("/notify/trade-plan-pending", json=_body())

    assert resp.status_code == 200
    assert resp.json()["delivered"] == 0
