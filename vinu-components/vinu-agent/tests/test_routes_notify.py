from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from vinu_agent.config import AgentConfig
from vinu_agent.server.routes_notify import router


@pytest.fixture(autouse=True)
def _fresh_noise_gate():
    # A33: the noise gate is a process-global singleton; give every test a
    # clean one so reservations / dedup state don't leak between tests.
    from vinu_agent.agent.notification_noise import NoiseConfig, NotificationNoiseGate, reset_noise_gate

    reset_noise_gate(NotificationNoiseGate(NoiseConfig()))
    yield
    reset_noise_gate(None)


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


def test_repeat_notice_for_same_plan_is_suppressed_by_dedup_window(client) -> None:
    # A33: a plan that keeps failing the gate shouldn't re-notify every worker cycle.
    from vinu_agent.agent.notification_noise import NoiseConfig, NotificationNoiseGate, reset_noise_gate

    reset_noise_gate(NotificationNoiseGate(NoiseConfig(dedup_window_sec=3600.0)))
    config = AgentConfig(telegram_token="tok", telegram_admin_chat_id="chat1")
    with patch("vinu_agent.server.routes_notify.load_config", return_value=config):
        with patch("vinu_agent.agent.notify_channels.HttpTelegramChannel.send_message", new_callable=AsyncMock) as tg_send:
            first = client.post("/notify/trade-plan-pending", json=_body(artifact_id="tp-dedup"))
            second = client.post("/notify/trade-plan-pending", json=_body(artifact_id="tp-dedup"))

    assert first.json()["status"] == "ok"
    assert first.json()["delivered"] == 1
    assert second.json()["status"] == "suppressed"
    assert second.json()["delivered"] == 0
    tg_send.assert_awaited_once()  # only the first call actually sent


def _drift_body(symbol="AAPL", action="alert_phantom_broker_position", book_qty=None, broker_qty=10.0):
    return {"symbol": symbol, "action": action, "book_qty": book_qty, "broker_qty": broker_qty}


def test_reconciliation_drift_no_channels_configured(client) -> None:
    with patch("vinu_agent.server.routes_notify.load_config", return_value=AgentConfig()):
        resp = client.post("/notify/reconciliation-drift", json=_drift_body())

    assert resp.status_code == 200
    assert resp.json() == {"status": "no_channels_configured", "delivered": 0}


def test_reconciliation_drift_delivers_and_describes_phantom_position(client) -> None:
    config = AgentConfig(discord_token="dtok", discord_admin_channel_id="999")
    with patch("vinu_agent.server.routes_notify.load_config", return_value=config):
        with patch("vinu_agent.agent.notify_channels.HttpDiscordChannel.send_message", new_callable=AsyncMock) as dc_send:
            resp = client.post("/notify/reconciliation-drift", json=_drift_body(broker_qty=12.5))

    assert resp.json()["delivered"] == 1
    sent_text = dc_send.await_args.args[1]
    assert "AAPL" in sent_text
    assert "12.5" in sent_text
    assert "NOT auto-corrected" in sent_text


def test_reconciliation_drift_describes_side_conflict(client) -> None:
    config = AgentConfig(discord_token="dtok", discord_admin_channel_id="999")
    with patch("vinu_agent.server.routes_notify.load_config", return_value=config):
        with patch("vinu_agent.agent.notify_channels.HttpDiscordChannel.send_message", new_callable=AsyncMock) as dc_send:
            resp = client.post(
                "/notify/reconciliation-drift",
                json=_drift_body(action="alert_side_conflict", book_qty=-5.0, broker_qty=5.0),
            )

    assert resp.json()["delivered"] == 1
    sent_text = dc_send.await_args.args[1]
    assert "disagree on side" in sent_text
    assert "never auto-flipped" in sent_text


def test_reconciliation_drift_repeat_for_same_symbol_and_action_is_suppressed(client) -> None:
    # A persisting phantom position must not re-notify every reconciliation
    # cycle -- only when it's newly detected (or the dedup window elapses).
    from vinu_agent.agent.notification_noise import NoiseConfig, NotificationNoiseGate, reset_noise_gate

    reset_noise_gate(NotificationNoiseGate(NoiseConfig(dedup_window_sec=3600.0)))
    config = AgentConfig(discord_token="dtok", discord_admin_channel_id="999")
    with patch("vinu_agent.server.routes_notify.load_config", return_value=config):
        with patch("vinu_agent.agent.notify_channels.HttpDiscordChannel.send_message", new_callable=AsyncMock) as dc_send:
            first = client.post("/notify/reconciliation-drift", json=_drift_body())
            second = client.post("/notify/reconciliation-drift", json=_drift_body())

    assert first.json()["status"] == "ok"
    assert second.json()["status"] == "suppressed"
    dc_send.assert_awaited_once()


def test_reconciliation_drift_different_symbols_do_not_suppress_each_other(client) -> None:
    from vinu_agent.agent.notification_noise import NoiseConfig, NotificationNoiseGate, reset_noise_gate

    reset_noise_gate(NotificationNoiseGate(NoiseConfig(dedup_window_sec=3600.0)))
    config = AgentConfig(discord_token="dtok", discord_admin_channel_id="999")
    with patch("vinu_agent.server.routes_notify.load_config", return_value=config):
        with patch("vinu_agent.agent.notify_channels.HttpDiscordChannel.send_message", new_callable=AsyncMock) as dc_send:
            a = client.post("/notify/reconciliation-drift", json=_drift_body(symbol="AAPL"))
            b = client.post("/notify/reconciliation-drift", json=_drift_body(symbol="MSFT"))

    assert a.json()["delivered"] == 1
    assert b.json()["delivered"] == 1
    assert dc_send.await_count == 2


def test_distinct_plans_do_not_suppress_each_other(client) -> None:
    from vinu_agent.agent.notification_noise import NoiseConfig, NotificationNoiseGate, reset_noise_gate

    reset_noise_gate(NotificationNoiseGate(NoiseConfig(dedup_window_sec=3600.0)))
    config = AgentConfig(telegram_token="tok", telegram_admin_chat_id="chat1")
    with patch("vinu_agent.server.routes_notify.load_config", return_value=config):
        with patch("vinu_agent.agent.notify_channels.HttpTelegramChannel.send_message", new_callable=AsyncMock) as tg_send:
            a = client.post("/notify/trade-plan-pending", json=_body(artifact_id="tp-a"))
            b = client.post("/notify/trade-plan-pending", json=_body(artifact_id="tp-b"))

    assert a.json()["delivered"] == 1
    assert b.json()["delivered"] == 1
    assert tg_send.await_count == 2
