from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from vinu_screener.scan.data_source import HttpStockDataSource


def _resp(json_body, status_ok=True):
    resp = MagicMock()
    resp.json.return_value = json_body
    if status_ok:
        resp.raise_for_status.return_value = None
    else:
        resp.raise_for_status.side_effect = RuntimeError("HTTP error")
    return resp


class TestHttpStockDataSource:
    def test_get_ohlcv_builds_a_frame_from_candle_rows(self) -> None:
        client = MagicMock()
        client.get.return_value = _resp({"count": 2, "data": [
            {"bar_ts": 1_700_000_000, "open": 10, "high": 11, "low": 9, "close": 10.5, "volume": 1000},
            {"bar_ts": 1_700_086_400, "open": 10.5, "high": 12, "low": 10, "close": 11.5, "volume": 1500},
        ]})
        ds = HttpStockDataSource(client, base_url="http://stock:8081")
        df = ds.get_ohlcv("AAPL")
        assert df is not None
        assert list(df.columns) == ["open", "high", "low", "close", "volume"]
        assert len(df) == 2
        assert df["close"].iloc[-1] == 11.5
        client.get.assert_called_once()
        assert "AAPL" in client.get.call_args.args[0]

    def test_empty_response_returns_none(self) -> None:
        client = MagicMock()
        client.get.return_value = _resp({"count": 0, "data": []})
        ds = HttpStockDataSource(client, base_url="http://stock:8081")
        assert ds.get_ohlcv("NOPE") is None

    def test_http_error_returns_none_not_raises(self) -> None:
        client = MagicMock()
        client.get.return_value = _resp({}, status_ok=False)
        ds = HttpStockDataSource(client, base_url="http://stock:8081")
        assert ds.get_ohlcv("AAPL") is None

    def test_transport_exception_returns_none(self) -> None:
        client = MagicMock()
        client.get.side_effect = ConnectionError("down")
        ds = HttpStockDataSource(client, base_url="http://stock:8081")
        assert ds.get_ohlcv("AAPL") is None

    def test_malformed_rows_missing_close_returns_none(self) -> None:
        client = MagicMock()
        client.get.return_value = _resp({"data": [{"bar_ts": 1, "open": 1}]})
        ds = HttpStockDataSource(client, base_url="http://stock:8081")
        assert ds.get_ohlcv("AAPL") is None

    def test_get_snapshot_derives_price_volume_dollar_volume(self) -> None:
        client = MagicMock()
        client.get.return_value = _resp({"data": [
            {"bar_ts": 1, "open": 10, "high": 11, "low": 9, "close": 20.0, "volume": 100.0},
        ]})
        ds = HttpStockDataSource(client, base_url="http://stock:8081")
        snap = ds.get_snapshot("AAPL")
        assert snap == {"price": 20.0, "volume": 100.0, "dollar_volume": 2000.0}

    def test_get_snapshot_none_when_no_data(self) -> None:
        client = MagicMock()
        client.get.return_value = _resp({"data": []})
        ds = HttpStockDataSource(client, base_url="http://stock:8081")
        assert ds.get_snapshot("AAPL") is None
