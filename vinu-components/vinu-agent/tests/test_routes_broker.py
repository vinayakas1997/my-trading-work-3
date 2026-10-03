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
    # C18: /broker/mandate/renew writes mandate.yaml -- point it at a tmp file
    import vinu_agent.broker.mandate as _mandate
    monkeypatch.setattr(_mandate, "DEFAULT_MANDATE_PATH", tmp_path / "mandate.yaml")
    # get_store() caches a module-level singleton backed by a real,
    # process-lifetime on-disk path (VINU_AGENT_DATA_ROOT, or /data, or
    # ~/.vinu) -- without resetting it, performance tests silently share
    # state across test runs (an artifact_id from a prior run's leftover
    # DB file makes "first write" tests see stale data) and can hit /data
    # permission errors in environments where that directory isn't
    # writable. Point it at a tmp file and clear the cached singleton so
    # each test gets a fresh, isolated store.
    import vinu_agent.broker.performance_store as _perf_store
    monkeypatch.setattr(_perf_store, "_store", None)
    monkeypatch.setattr(_perf_store, "_persistent_path", lambda: tmp_path / "paper_performance.db")
    app = FastAPI()
    app.include_router(routes_broker.router)
    return TestClient(app)


class TestMandateConsentRenewal:
    def test_renew_by_days_writes_future_expiry(self, client) -> None:
        from datetime import datetime, timezone

        resp = client.post("/broker/mandate/renew", json={"days": 14})
        assert resp.status_code == 200
        exp = datetime.fromisoformat(resp.json()["consent_expires_at"])
        assert exp > datetime.now(timezone.utc)

    def test_renew_with_explicit_until(self, client) -> None:
        resp = client.post("/broker/mandate/renew", json={"until": "2099-01-01T00:00:00+00:00"})
        assert resp.status_code == 200
        assert resp.json()["consent_expires_at"].startswith("2099-01-01")

    def test_renew_rejects_a_bad_timestamp(self, client) -> None:
        resp = client.post("/broker/mandate/renew", json={"until": "soon"})
        assert resp.status_code == 422

    def test_get_mandate_reflects_the_renewal(self, client) -> None:
        client.post("/broker/mandate/renew", json={"until": "2099-01-01T00:00:00+00:00"})
        body = client.get("/broker/mandate").json()["mandate"]
        assert body["consent_expires_at"].startswith("2099-01-01")
        assert body["consent_expired"] is False

    def test_renew_preserves_other_mandate_keys(self, client, tmp_path) -> None:
        (tmp_path / "mandate.yaml").write_text("max_order_value: 12345.0\nallow_short: true\n")
        client.post("/broker/mandate/renew", json={"days": 7})
        import yaml
        raw = yaml.safe_load((tmp_path / "mandate.yaml").read_text())
        assert raw["max_order_value"] == 12345.0
        assert raw["allow_short"] is True
        assert "consent_expires_at" in raw


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


class TestAppendDailyReturnRoute:
    """Regression for the dead ShadowEvaluator promotion gate: nothing in
    production ever called this or the bulk POST above, so
    PaperPerformanceStore stayed permanently empty (see high-expectations
    gate-conflict audit)."""

    def test_appends_a_single_day(self, client) -> None:
        resp = client.post(
            "/broker/performance/art-append-1/append",
            json={"daily_return": 0.012, "trade_date": "2026-09-14"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["n_returns"] == 1

        resp = client.get("/broker/performance/art-append-1")
        assert resp.json()["daily_returns"] == [0.012]

    def test_appends_accumulate_across_days(self, client) -> None:
        client.post("/broker/performance/art-append-2/append", json={"daily_return": 0.01, "trade_date": "2026-09-10"})
        client.post("/broker/performance/art-append-2/append", json={"daily_return": -0.02, "trade_date": "2026-09-11"})
        resp = client.get("/broker/performance/art-append-2")
        assert resp.json()["daily_returns"] == [0.01, -0.02]

    def test_same_trade_date_is_idempotent(self, client) -> None:
        client.post("/broker/performance/art-append-3/append", json={"daily_return": 0.01, "trade_date": "2026-09-14"})
        resp = client.post(
            "/broker/performance/art-append-3/append",
            json={"daily_return": 0.99, "trade_date": "2026-09-14"},
        )
        assert resp.json()["status"] == "already_recorded"

        resp = client.get("/broker/performance/art-append-3")
        assert resp.json()["daily_returns"] == [0.01]  # the 0.99 second call never applied

    def test_invalid_trade_date_is_422(self, client) -> None:
        resp = client.post(
            "/broker/performance/art-append-4/append",
            json={"daily_return": 0.01, "trade_date": "not-a-date"},
        )
        assert resp.status_code == 422

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


class TestBrokerOrderLookupRoute:
    """GET /broker/order/{id}: one order's state at the broker, including its average fill price (the input
    vinu-live's order ledger needs to compute slippage). Problems are reported in the body, never as a 5xx."""

    def _order(self, **kw):
        from vinu_agent.broker.alpaca import Order

        base = dict(order_id="ord-1", symbol="AAPL", side="buy", type="market", status="filled", qty=10.0,
                    filled_qty=10.0, limit_price=None, stop_price=None, created_at="t0", updated_at="t1",
                    filled_avg_price=187.31)
        base.update(kw)
        return Order(**base)

    def test_returns_status_quantity_and_the_average_fill_price(self, client) -> None:
        broker = MagicMock()
        broker.is_configured.return_value = True
        broker.get_order.return_value = self._order()
        with patch("vinu_agent.server.routes_broker.get_live_broker", return_value=broker):
            body = client.get("/broker/order/ord-1").json()
        broker.get_order.assert_called_once_with("ord-1")
        assert body["status"] == "ok" and body["order_status"] == "filled"
        assert body["filled_qty"] == 10.0 and body["filled_avg_price"] == 187.31 and body["symbol"] == "AAPL"

    def test_a_working_order_has_no_fill_price_yet(self, client) -> None:
        broker = MagicMock()
        broker.is_configured.return_value = True
        broker.get_order.return_value = self._order(status="accepted", filled_qty=0.0, filled_avg_price=None)
        with patch("vinu_agent.server.routes_broker.get_live_broker", return_value=broker):
            body = client.get("/broker/order/ord-1").json()
        assert body["order_status"] == "accepted" and body["filled_avg_price"] is None

    def test_unconfigured_and_errors_are_reported_in_the_body(self, client) -> None:
        broker = MagicMock()
        broker.is_configured.return_value = False
        with patch("vinu_agent.server.routes_broker.get_live_broker", return_value=broker):
            r = client.get("/broker/order/x")
        assert r.status_code == 200 and r.json() == {"configured": False, "status": "unconfigured"}
        broker.is_configured.return_value = True
        broker.get_order.side_effect = RuntimeError("alpaca 404")
        with patch("vinu_agent.server.routes_broker.get_live_broker", return_value=broker):
            r = client.get("/broker/order/x")
        assert r.status_code == 200 and r.json()["status"] == "error" and "alpaca 404" in r.json()["error"]

    def test_a_broker_without_order_lookup_says_so(self, client) -> None:
        broker = MagicMock(spec=["is_configured"])
        broker.is_configured.return_value = True
        with patch("vinu_agent.server.routes_broker.get_live_broker", return_value=broker):
            body = client.get("/broker/order/x").json()
        assert body["status"] == "error" and "cannot look up" in body["error"]

    def test_the_alpaca_broker_calls_the_order_by_id_endpoint(self) -> None:
        from vinu_agent.broker.alpaca import AlpacaBroker

        b = AlpacaBroker()
        b._get = MagicMock(return_value={"id": "o9", "symbol": "MSFT", "side": "sell", "type": "market", "status": "filled",
                                         "qty": "3", "filled_qty": "3", "filled_avg_price": "400.5",
                                         "created_at": "a", "updated_at": "b"})
        o = b.get_order("o9")
        b._get.assert_called_once_with("/v2/orders/o9")
        assert o.order_id == "o9" and o.filled_avg_price == 400.5 and o.filled_qty == 3.0
