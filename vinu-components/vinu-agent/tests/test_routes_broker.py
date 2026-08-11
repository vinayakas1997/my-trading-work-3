import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from vinu_agent.broker import kill_switch
from vinu_agent.broker.alpaca import Account
import vinu_agent.server.routes_broker as routes_broker


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(kill_switch, "KILL_SWITCH_PATH", tmp_path / "vinu-trading-halt")
    monkeypatch.setattr(kill_switch, "KILL_SWITCH_DIR", tmp_path / "vinu-trading-halt.d")
    app = FastAPI()
    app.include_router(routes_broker.router)
    return TestClient(app)


class TestBrokerRoutes:
    def test_status_defaults_to_not_halted(self, client) -> None:
        resp = client.get("/broker/status")
        assert resp.status_code == 200
        assert resp.json() == {"halted": False, "scope": None}

    def test_halt_then_status_reflects_it(self, client) -> None:
        resp = client.post("/broker/halt", json={"reason": "test halt"})
        assert resp.status_code == 200
        assert resp.json()["halted"] is True

        resp = client.get("/broker/status")
        assert resp.json()["halted"] is True

    def test_halt_with_empty_body(self, client) -> None:
        resp = client.post("/broker/halt")
        assert resp.status_code == 200
        assert resp.json()["halted"] is True

    def test_resume_clears_halt(self, client) -> None:
        client.post("/broker/halt")
        resp = client.post("/broker/resume")
        assert resp.status_code == 200
        assert resp.json()["halted"] is False

        resp = client.get("/broker/status")
        assert resp.json()["halted"] is False

    def test_scoped_halt_does_not_affect_global_status(self, client) -> None:
        client.post("/broker/halt", json={"scope": "AAPL"})

        resp = client.get("/broker/status")
        assert resp.json()["halted"] is False

        resp = client.get("/broker/status", params={"scope": "AAPL"})
        assert resp.json()["halted"] is True


class TestBrokerAccountRoute:
    def test_returns_not_configured_without_credentials(self, client) -> None:
        resp = client.get("/broker/account")
        assert resp.status_code == 200
        body = resp.json()
        assert body["configured"] is False
        assert body["equity"] is None

    def test_returns_equity_when_configured(self, client) -> None:
        account = Account(
            account_id="acc1", status="ACTIVE", currency="USD",
            cash=50_000.0, portfolio_value=100_000.0, buying_power=50_000.0,
            equity=100_000.0, daytrade_count=0, pattern_day_trader=False,
        )
        mock_broker = MagicMock()
        mock_broker.is_configured.return_value = True
        mock_broker.get_account.return_value = account

        with patch("vinu_agent.server.routes_broker.get_live_broker", return_value=mock_broker):
            resp = client.get("/broker/account")

        assert resp.status_code == 200
        body = resp.json()
        assert body["configured"] is True
        assert body["equity"] == 100_000.0
        assert body["cash"] == 50_000.0

    def test_handles_broker_error_gracefully(self, client) -> None:
        mock_broker = MagicMock()
        mock_broker.is_configured.return_value = True
        mock_broker.get_account.side_effect = RuntimeError("Alpaca unreachable")

        with patch("vinu_agent.server.routes_broker.get_live_broker", return_value=mock_broker):
            resp = client.get("/broker/account")

        assert resp.status_code == 200
        body = resp.json()
        assert body["configured"] is True
        assert body["equity"] is None
        assert "error" in body


class TestBrokerPositionsRoute:
    def test_returns_empty_when_not_configured(self, client) -> None:
        resp = client.get("/broker/positions")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_positions_when_configured(self, client) -> None:
        from vinu_agent.broker.alpaca import Position

        position = Position(
            symbol="AAPL", qty=10.0, market_value=1500.0, cost_basis=1400.0,
            unrealized_pl=100.0, unrealized_plpc=0.07, current_price=150.0, avg_entry_price=140.0,
        )
        mock_broker = MagicMock()
        mock_broker.is_configured.return_value = True
        mock_broker.get_positions.return_value = [position]

        with patch("vinu_agent.server.routes_broker.get_live_broker", return_value=mock_broker):
            resp = client.get("/broker/positions")

        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["symbol"] == "AAPL"
        assert body[0]["qty"] == 10.0


class TestBrokerOrderRoute:
    def test_delegates_to_trade_tool_and_returns_its_json(self, client) -> None:
        mock_tool = MagicMock()
        mock_tool.execute.return_value = json.dumps({"status": "rejected", "reason": "test reason"})

        with patch("vinu_agent.server.routes_broker.TradeTool", return_value=mock_tool):
            resp = client.post("/broker/order", json={"symbol": "AAPL", "side": "buy", "qty": 10})

        assert resp.status_code == 200
        assert resp.json() == {"status": "rejected", "reason": "test reason"}
        mock_tool.execute.assert_called_once()
        call_kwargs = mock_tool.execute.call_args.kwargs
        assert call_kwargs["symbol"] == "AAPL"
        assert call_kwargs["qty"] == 10

    def test_performance_returns_empty_for_unknown_artifact(self, client) -> None:
        resp = client.get("/broker/performance/unknown-artifact")
        assert resp.status_code == 200
        body = resp.json()
        assert body["artifact_id"] == "unknown-artifact"
        assert body["daily_returns"] == []

    def test_record_then_get_performance(self, client) -> None:
        resp = client.post(
            "/broker/performance/art-1",
            json={"daily_returns": [0.01, -0.005, 0.02, 0.0, -0.01]},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
        assert resp.json()["n_returns"] == 5

        resp = client.get("/broker/performance/art-1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["artifact_id"] == "art-1"
        assert body["daily_returns"] == [0.01, -0.005, 0.02, 0.0, -0.01]

    def test_record_overwrites_previous_data(self, client) -> None:
        client.post("/broker/performance/art-2", json={"daily_returns": [0.1, 0.2]})
        client.post("/broker/performance/art-2", json={"daily_returns": [0.3, 0.4, 0.5]})
        resp = client.get("/broker/performance/art-2")
        assert resp.json()["daily_returns"] == [0.3, 0.4, 0.5]

    def test_passes_bracket_order_fields_through(self, client) -> None:
        mock_tool = MagicMock()
        mock_tool.execute.return_value = json.dumps({"status": "submitted"})

        with patch("vinu_agent.server.routes_broker.TradeTool", return_value=mock_tool):
            resp = client.post("/broker/order", json={
                "symbol": "AAPL", "side": "buy", "qty": 10,
                "take_profit_price": 150.0, "stop_loss_price": 130.0,
            })

        assert resp.status_code == 200
        call_kwargs = mock_tool.execute.call_args.kwargs
        assert call_kwargs["take_profit_price"] == 150.0
        assert call_kwargs["stop_loss_price"] == 130.0
