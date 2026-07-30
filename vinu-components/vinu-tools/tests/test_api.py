"""HTTP API tests."""

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from vinu_tools.server.app import create_app
from vinu_tools.service import FeatureService
from tests.conftest import MockCandleClient


def test_api_submit_and_run(config, backend):
    service = FeatureService(config=config, storage=backend, candle_client=MockCandleClient())
    app = create_app(service)
    client = TestClient(app)

    resp = client.post(
        "/features/requests",
        json={
            "title": "api_test",
            "symbols": ["AAPL"],
            "from_ts": 1_700_000_000,
            "to_ts": 1_700_043_200,
            "preset": "basic_ta",
            "run_immediately": True,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "done"
    assert body["file_path"]

    resp2 = client.get("/features/requests/by-title/api_test")
    assert resp2.status_code == 200
    assert resp2.json()["title"] == "api_test"

    resp3 = client.get("/features/presets")
    assert resp3.status_code == 200
    assert resp3.json()["count"] >= 1

    service.close()


def test_feature_for_symbol(config, backend):
    service = FeatureService(config=config, storage=backend, candle_client=MockCandleClient())
    app = create_app(service)
    client = TestClient(app)

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": [
            {"ts": 1_700_000_000, "open": 100, "high": 101, "low": 99,
             "close": 100.5, "volume": 1000, "signal": 0.5},
        ]
    }
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.get.return_value = mock_response

    with patch("httpx.AsyncClient", return_value=mock_client):
        resp = client.get("/features/features/AAPL?indicators=signal")

    assert resp.status_code == 200
    body = resp.json()
    assert body["symbol"] == "AAPL"
    assert body["signal"] == 0.5
    assert body["values"]["signal"] == 0.5

    service.close()


def test_feature_for_symbol_upstream_error(config, backend):
    service = FeatureService(config=config, storage=backend, candle_client=MockCandleClient())
    app = create_app(service)
    client = TestClient(app)

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.get.side_effect = Exception("upstream timeout")

    with patch("httpx.AsyncClient", return_value=mock_client):
        resp = client.get("/features/features/AAPL?indicators=signal")

    assert resp.status_code == 502
    body = resp.json()
    assert "upstream timeout" in body["detail"]

    service.close()

