"""HTTP API tests."""

from fastapi.testclient import TestClient

from vinu_features.server.app import create_app
from vinu_features.service import FeatureService


class MockCandleClient:
    def fetch_candles(self, symbol, *, interval, from_ts, to_ts, limit=50000):
        ts = from_ts or 1_700_000_000
        end = to_ts or ts + 86400 * 30
        rows = []
        while ts <= end:
            price = 100.0
            rows.append(
                {
                    "ts": ts,
                    "open": price,
                    "high": price,
                    "low": price,
                    "close": price,
                    "volume": 1,
                }
            )
            ts += 86400
        return rows


def test_api_submit_and_run(config, backend):
    service = FeatureService(config=config, storage=backend, candle_client=MockCandleClient())
    app = create_app(service)
    client = TestClient(app)

    resp = client.post(
        "/requests",
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

    resp2 = client.get("/requests/by-title/api_test")
    assert resp2.status_code == 200
    assert resp2.json()["title"] == "api_test"

    resp3 = client.get("/presets")
    assert resp3.status_code == 200
    assert resp3.json()["count"] >= 1

    service.close()
