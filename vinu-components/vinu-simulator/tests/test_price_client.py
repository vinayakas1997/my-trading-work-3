"""item #13 finding #6: `clients/price_client.py`'s thread-pool fan-out and
missing-symbol error path had zero dedicated tests."""

from __future__ import annotations

import pandas as pd
import pytest

from vinu_simulator.clients.price_client import PriceClient


def _candles(bar_ts: list[int], close: list[float], volume: list[float]) -> dict:
    return {
        "data": [
            {"bar_ts": t, "open": c, "high": c, "low": c, "close": c, "volume": v}
            for t, c, v in zip(bar_ts, close, volume)
        ]
    }


class TestGetOhclv:
    def test_fetches_each_symbol_and_shapes_a_dataframe_per_symbol(self) -> None:
        client = PriceClient(base_url="http://prices.invalid")

        def _get(path: str, params=None):
            sym = path.rsplit("/", 1)[-1]
            return _candles([0, 86400], [100.0 + len(sym), 101.0], [1000.0, 1100.0])

        client.get = _get
        result = client.get_ohclv(["AAPL", "MSFT"], "2020-01-01", "2020-01-05")

        assert set(result.keys()) == {"AAPL", "MSFT"}
        assert list(result["AAPL"].columns) == ["open", "high", "low", "close", "volume"]
        assert len(result["AAPL"]) == 2

    def test_a_symbol_whose_fetch_raises_is_dropped_not_propagated(self) -> None:
        client = PriceClient(base_url="http://prices.invalid")

        def _get(path: str, params=None):
            if "BAD" in path:
                raise RuntimeError("upstream 500")
            return _candles([0], [100.0], [1000.0])

        client.get = _get
        result = client.get_ohclv(["AAPL", "BAD"], "2020-01-01", "2020-01-05")

        assert set(result.keys()) == {"AAPL"}

    def test_empty_or_missing_data_key_is_dropped_not_a_crash(self) -> None:
        client = PriceClient(base_url="http://prices.invalid")
        client.get = lambda path, params=None: {"data": []}
        result = client.get_ohclv(["AAPL"], "2020-01-01", "2020-01-05")
        assert result == {}

        client.get = lambda path, params=None: None
        result = client.get_ohclv(["AAPL"], "2020-01-01", "2020-01-05")
        assert result == {}

    def test_keeps_only_requested_indicator_columns_that_exist(self) -> None:
        client = PriceClient(base_url="http://prices.invalid")

        def _get(path: str, params=None):
            recs = _candles([0, 86400], [100.0, 101.0], [1000.0, 1100.0])
            for row in recs["data"]:
                row["rsi_14"] = 55.0
            return recs

        client.get = _get
        result = client.get_ohclv(["AAPL"], "2020-01-01", "2020-01-05", indicators=["rsi_14", "not_a_real_column"])
        assert "rsi_14" in result["AAPL"].columns
        assert "not_a_real_column" not in result["AAPL"].columns


class TestOhclvCache:
    """item #13 finding #4: identical requests should not re-hit the
    network."""

    def test_repeated_identical_request_does_not_refetch(self) -> None:
        client = PriceClient(base_url="http://prices.invalid")
        calls = {"n": 0}

        def _get(path: str, params=None):
            calls["n"] += 1
            return _candles([0], [100.0], [1000.0])

        client.get = _get
        client.get_ohclv(["AAPL"], "2020-01-01", "2020-01-05")
        client.get_ohclv(["AAPL"], "2020-01-01", "2020-01-05")

        assert calls["n"] == 1

    def test_a_failed_fetch_is_not_cached_so_the_next_call_asks_again(self) -> None:
        """A transient failure used to be cached with no expiry: every later
        call for that date range returned "no data" without contacting the
        stock API, which made all walk-forward windows fail."""
        client = PriceClient(base_url="http://prices.invalid")
        calls = {"n": 0}

        def _get(path: str, params=None):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("stock api briefly unavailable")
            return _candles([0], [100.0], [1000.0])

        client.get = _get
        assert client.get_ohclv(["AAPL"], "2020-01-01", "2020-01-05") == {}
        again = client.get_ohclv(["AAPL"], "2020-01-01", "2020-01-05")

        assert "AAPL" in again and calls["n"] == 2

    def test_symbol_order_does_not_defeat_the_cache(self) -> None:
        client = PriceClient(base_url="http://prices.invalid")
        calls = {"n": 0}

        def _get(path: str, params=None):
            calls["n"] += 1
            return _candles([0], [100.0], [1000.0])

        client.get = _get
        client.get_ohclv(["AAPL", "MSFT"], "2020-01-01", "2020-01-05")
        client.get_ohclv(["MSFT", "AAPL"], "2020-01-01", "2020-01-05")

        assert calls["n"] == 2  # one fetch per symbol, not per call

    def test_different_date_range_is_a_real_cache_miss(self) -> None:
        client = PriceClient(base_url="http://prices.invalid")
        calls = {"n": 0}

        def _get(path: str, params=None):
            calls["n"] += 1
            return _candles([0], [100.0], [1000.0])

        client.get = _get
        client.get_ohclv(["AAPL"], "2020-01-01", "2020-01-05")
        client.get_ohclv(["AAPL"], "2020-02-01", "2020-02-05")

        assert calls["n"] == 2

    def test_cache_hit_returns_an_independent_copy_not_a_shared_frame(self) -> None:
        client = PriceClient(base_url="http://prices.invalid")
        client.get = lambda path, params=None: _candles([0], [100.0], [1000.0])

        first = client.get_ohclv(["AAPL"], "2020-01-01", "2020-01-05")
        second = client.get_ohclv(["AAPL"], "2020-01-01", "2020-01-05")
        second["AAPL"].iloc[0, 0] = 999.0

        assert first["AAPL"].iloc[0, 0] == pytest.approx(100.0)


class TestFetchPriceDataCache:
    def test_repeated_identical_request_does_not_refetch(self) -> None:
        client = PriceClient(base_url="http://prices.invalid")
        calls = {"n": 0}

        def _get(path: str, params=None):
            calls["n"] += 1
            return _candles([0], [100.0], [1000.0])

        client.get = _get
        client.get_price_and_volume(["AAPL"], "2020-01-01", "2020-01-05")
        client.get_price_and_volume(["AAPL"], "2020-01-01", "2020-01-05")

        assert calls["n"] == 1

    def test_different_symbol_order_is_a_real_cache_miss_not_reordered_columns(self) -> None:
        # Column order in the returned frame is meaningful (selected by the
        # exact requested `symbols` list) -- a differently-ordered request
        # must refetch, not silently reuse a cached frame with the wrong
        # column order.
        client = PriceClient(base_url="http://prices.invalid")

        def _get(path: str, params=None):
            sym = path.rsplit("/", 1)[-1]
            base = 100.0 if sym == "AAPL" else 200.0
            return _candles([0], [base], [1000.0])

        client.get = _get
        prices_a, _ = client.get_price_and_volume(["AAPL", "MSFT"], "2020-01-01", "2020-01-05")
        prices_b, _ = client.get_price_and_volume(["MSFT", "AAPL"], "2020-01-01", "2020-01-05")

        assert list(prices_a.columns) == ["AAPL", "MSFT"]
        assert list(prices_b.columns) == ["MSFT", "AAPL"]


class TestFetchPriceData:
    def test_all_symbols_failing_raises_value_error(self) -> None:
        client = PriceClient(base_url="http://prices.invalid")
        client.get = lambda path, params=None: None
        with pytest.raises(ValueError, match="No price data found"):
            client.get_prices(["AAPL", "MSFT"], "2020-01-01", "2020-01-05")

    def test_a_missing_symbol_raises_value_error_listing_it(self) -> None:
        client = PriceClient(base_url="http://prices.invalid")

        def _get(path: str, params=None):
            if "MSFT" in path:
                return None
            return _candles([0, 86400], [100.0, 101.0], [1000.0, 1100.0])

        client.get = _get
        with pytest.raises(ValueError, match=r"Tickers missing from price data: \['MSFT'\]"):
            client.get_prices(["AAPL", "MSFT"], "2020-01-01", "2020-01-05")

    def test_get_price_and_volume_returns_aligned_frames_for_present_symbols(self) -> None:
        client = PriceClient(base_url="http://prices.invalid")

        def _get(path: str, params=None):
            sym = path.rsplit("/", 1)[-1]
            base = 100.0 if sym == "AAPL" else 200.0
            return _candles([0, 86400], [base, base + 1.0], [1000.0, 1100.0])

        client.get = _get
        prices, volumes = client.get_price_and_volume(["AAPL", "MSFT"], "2020-01-01", "2020-01-05")

        assert list(prices.columns) == ["AAPL", "MSFT"]
        assert list(volumes.columns) == ["AAPL", "MSFT"]
        assert len(prices) == 2
        assert prices["AAPL"].iloc[0] == pytest.approx(100.0)
        assert prices["MSFT"].iloc[0] == pytest.approx(200.0)
