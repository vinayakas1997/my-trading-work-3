"""Tests for feature catalog and structured feature specs."""

import pytest
from fastapi.testclient import TestClient

from vinu_features.compute.feature_catalog import format_help, list_indicators
from vinu_features.compute.feature_spec import validate_and_resolve
from vinu_features.compute.registry import apply_indicators
from vinu_features.server.app import create_app
from vinu_features.service import FeatureService


def test_feature_catalog_lists_all_indicators():
    assert len(list_indicators()) == 23


def test_features_help_rsi_shows_period_default():
    text = format_help("rsi")
    assert "period" in text
    assert "14" in text
    assert "--feature rsi:period=20" in text


def test_resolve_rsi_period_20_from_object():
    cols = validate_and_resolve([{"kind": "rsi", "params": {"period": 20}}])
    assert cols == ["rsi_20"]


def test_resolve_legacy_rsi_14_unchanged():
    cols = validate_and_resolve(["rsi_14"])
    assert cols == ["rsi_14"]


def test_resolve_rsi_colon_spec():
    cols = validate_and_resolve(["rsi:period=20"])
    assert cols == ["rsi_20"]


def test_submit_rejects_unknown_kind():
    with pytest.raises(ValueError, match="Unknown indicator"):
        validate_and_resolve(["not_an_indicator:period=1"])


def test_submit_rejects_invalid_period():
    with pytest.raises(ValueError, match="must be >="):
        validate_and_resolve([{"kind": "rsi", "params": {"period": 1}}])


def test_rsi_20_computes():
    rows = []
    for i in range(50):
        p = 100.0 + i * 0.5
        rows.append(
            {
                "ts": 1_700_000_000 + i * 86400,
                "symbol": "AAPL",
                "open": p,
                "high": p + 1,
                "low": p - 1,
                "close": p,
                "volume": 1000,
            }
        )
    out = apply_indicators(rows, ["rsi_20"])
    assert out[25]["rsi_20"] is not None


def test_bollinger_custom_period():
    cols = validate_and_resolve(["bollinger:period=30"])
    assert "bb_upper_30" in cols
    assert "bb_mid_30" in cols
    assert "bb_lower_30" in cols


def test_error_suggests_help_for_typo():
    with pytest.raises(ValueError, match="Did you mean 'rsi'?"):
        validate_and_resolve(["rsii:period=14"])


class _MockCandles:
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


def test_http_invalid_spec_returns_400_with_message(config, backend):
    service = FeatureService(config=config, storage=backend, candle_client=_MockCandles())
    client = TestClient(create_app(service))
    resp = client.post(
        "/requests",
        json={
            "title": "bad_spec",
            "symbols": ["AAPL"],
            "from_ts": 1_700_000_000,
            "to_ts": 1_700_043_200,
            "features": [{"kind": "rsii", "params": {"period": 14}}],
        },
    )
    assert resp.status_code == 400
    assert "rsii" in resp.json()["detail"].lower() or "Unknown indicator" in resp.json()["detail"]
    service.close()


def test_http_features_catalog(config, backend):
    service = FeatureService(config=config, storage=backend, candle_client=_MockCandles())
    client = TestClient(create_app(service))
    resp = client.get("/features")
    assert resp.status_code == 200
    assert resp.json()["count"] == 23
    service.close()
