from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import vinu_agent.server.routes_options as routes_options


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(routes_options.router)
    return TestClient(app)


class TestGetOptionsSnapshot:
    def test_returns_ok_with_contracts(self, client: TestClient) -> None:
        rows = [{"contract_symbol": "AAPL240119C00190000", "implied_volatility": 0.32}]
        with patch("vinu_agent.server.routes_options.fetch_chain", return_value=rows) as mock_fetch:
            resp = client.get("/options/aapl/snapshot")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["symbol"] == "AAPL"
        assert body["n_contracts"] == 1
        assert body["contracts"] == rows
        # Symbol is upper-cased before reaching fetch_chain.
        mock_fetch.assert_called_once_with("AAPL", 100, None)

    def test_empty_chain_reports_empty_status_not_error(self, client: TestClient) -> None:
        with patch("vinu_agent.server.routes_options.fetch_chain", return_value=[]):
            resp = client.get("/options/ZZZZ/snapshot")
        assert resp.status_code == 200
        assert resp.json() == {"status": "empty", "symbol": "ZZZZ", "n_contracts": 0, "contracts": []}

    def test_fetch_failure_reports_error_status_not_5xx(self, client: TestClient) -> None:
        with patch("vinu_agent.server.routes_options.fetch_chain", side_effect=PermissionError("no entitlement")):
            resp = client.get("/options/AAPL/snapshot")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "error"
        assert "no entitlement" in body["error"]

    def test_expiration_and_limit_query_params_forwarded(self, client: TestClient) -> None:
        with patch("vinu_agent.server.routes_options.fetch_chain", return_value=[]) as mock_fetch:
            client.get("/options/AAPL/snapshot", params={"expiration": "2024-06-21", "limit": 5})
        mock_fetch.assert_called_once_with("AAPL", 5, "2024-06-21")
