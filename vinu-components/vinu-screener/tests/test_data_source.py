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


class TestGetOhlcvBatch:
    def test_one_post_call_returns_a_frame_per_symbol(self) -> None:
        client = MagicMock()
        client.post.return_value = _resp({"results": {
            "AAPL": {"count": 1, "data": [{"bar_ts": 1, "open": 1, "high": 2, "low": 0.5, "close": 1.5, "volume": 100}]},
            "MSFT": {"count": 1, "data": [{"bar_ts": 1, "open": 2, "high": 3, "low": 1.5, "close": 2.5, "volume": 200}]},
        }})
        ds = HttpStockDataSource(client, base_url="http://stock:8081")
        out = ds.get_ohlcv_batch(["AAPL", "MSFT"])
        assert client.post.call_count == 1
        assert out["AAPL"]["close"].iloc[-1] == 1.5
        assert out["MSFT"]["close"].iloc[-1] == 2.5

    def test_symbol_missing_from_response_is_none(self) -> None:
        client = MagicMock()
        client.post.return_value = _resp({"results": {"AAPL": {"count": 0, "data": []}}})
        ds = HttpStockDataSource(client, base_url="http://stock:8081")
        out = ds.get_ohlcv_batch(["AAPL", "GHOST"])
        assert out["AAPL"] is None
        assert out["GHOST"] is None

    def test_every_requested_symbol_has_an_entry(self) -> None:
        client = MagicMock()
        client.post.return_value = _resp({"results": {}})
        ds = HttpStockDataSource(client, base_url="http://stock:8081")
        out = ds.get_ohlcv_batch(["AAPL", "MSFT"])
        assert set(out.keys()) == {"AAPL", "MSFT"}

    def test_transport_failure_degrades_every_symbol_to_none_not_raises(self) -> None:
        client = MagicMock()
        client.post.side_effect = ConnectionError("down")
        ds = HttpStockDataSource(client, base_url="http://stock:8081")
        out = ds.get_ohlcv_batch(["AAPL", "MSFT"])
        assert out == {"AAPL": None, "MSFT": None}

    def test_http_error_degrades_every_symbol_to_none(self) -> None:
        client = MagicMock()
        client.post.return_value = _resp({}, status_ok=False)
        ds = HttpStockDataSource(client, base_url="http://stock:8081")
        out = ds.get_ohlcv_batch(["AAPL"])
        assert out == {"AAPL": None}

    def test_large_universe_is_split_into_multiple_chunk_calls(self) -> None:
        client = MagicMock()
        client.post.return_value = _resp({"results": {}})
        ds = HttpStockDataSource(client, base_url="http://stock:8081")
        symbols = [f"S{i}" for i in range(1100)]  # 3 chunks at BATCH_CHUNK_SIZE=500
        ds.get_ohlcv_batch(symbols)
        assert client.post.call_count == 3

    def test_lowercase_input_symbols_come_back_uppercased(self) -> None:
        client = MagicMock()
        client.post.return_value = _resp({"results": {
            "AAPL": {"count": 1, "data": [{"bar_ts": 1, "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1}]},
        }})
        ds = HttpStockDataSource(client, base_url="http://stock:8081")
        out = ds.get_ohlcv_batch(["aapl"])
        assert "AAPL" in out
        assert out["AAPL"] is not None
