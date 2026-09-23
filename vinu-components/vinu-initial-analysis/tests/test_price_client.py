from __future__ import annotations

from unittest.mock import MagicMock, patch

from vinu_initial_analysis.clients.local_price_client import LocalPriceClient
from vinu_initial_analysis.clients.price_client import _INTERVAL_MAP, PriceClient

# Every real angle time_format that a caller might pass through to a
# price client -- confirmed against vinu-stock-price's own
# INTERVAL_SECONDS/_bucket_fn_for (aggregate.py), the actual set of
# interval strings that resolve without raising "Unsupported interval".
_REAL_ANGLE_TIME_FORMATS = ["1min", "5min", "15min", "1H", "4H", "1D", "1W", "1M", "6M"]


class TestIntervalMap:
    def test_5min_is_mapped(self) -> None:
        """Real bug found 2026-09-23: every one of the 28 real angles
        declares "5min", but _INTERVAL_MAP had no entry for it -- it was
        sent to vinu-stock-price unmapped, which only accepts "5m" and
        raises "Unsupported interval: 5min" for anything else. Caught by
        _fetch_bars's blanket except, this silently returned empty bars
        for every angle's 5min timeframe, forever, on every scheduled
        run."""
        assert _INTERVAL_MAP["5min"] == "5m"

    def test_every_real_angle_time_format_maps_to_something_vinu_stock_price_accepts(self) -> None:
        # vinu-stock-price's own accepted keys, duplicated here rather than
        # imported to keep this a real cross-service contract check, not a
        # tautology against the same source.
        accepted = {"1m", "5m", "15m", "30m", "1h", "4h", "1d", "1wk", "1mo", "6mo"}
        for fmt in _REAL_ANGLE_TIME_FORMATS:
            mapped = _INTERVAL_MAP.get(fmt, fmt)
            assert mapped.lower() in accepted, f"{fmt!r} maps to {mapped!r}, not accepted"


class TestPriceClientGetCandles:
    def test_5min_request_sends_5m_to_the_real_api(self) -> None:
        client = PriceClient("http://svc")
        with patch("vinu_initial_analysis.clients.price_client.request") as mock_request:
            resp = MagicMock()
            resp.json.return_value = {"data": []}
            mock_request.return_value = resp
            client.get_candles("AAPL", interval="5min")
        _, kwargs = mock_request.call_args
        assert kwargs["params"]["interval"] == "5m"


class TestLocalPriceClientGetCandles:
    def test_interval_is_mapped_before_reaching_fetch_candles(self) -> None:
        """Real bug found 2026-09-23: LocalPriceClient passed `interval`
        straight through with no mapping at all -- every real angle
        time_format except "1H"/"4H"/"1D" (which happen to lowercase into
        what vinu-stock-price accepts) would raise inside fetch_candles."""
        client = LocalPriceClient("/tmp/does-not-matter", ["AAPL"])
        with patch("vinu_initial_analysis.clients.local_price_client.fetch_candles") as mock_fetch:
            mock_fetch.return_value = []
            client.get_candles("AAPL", interval="5min")
        _, kwargs = mock_fetch.call_args
        assert kwargs["interval"] == "5m"

    def test_every_real_angle_time_format_is_mapped(self) -> None:
        client = LocalPriceClient("/tmp/does-not-matter", ["AAPL"])
        accepted = {"1m", "5m", "15m", "30m", "1h", "4h", "1d", "1wk", "1mo", "6mo"}
        with patch("vinu_initial_analysis.clients.local_price_client.fetch_candles") as mock_fetch:
            mock_fetch.return_value = []
            for fmt in _REAL_ANGLE_TIME_FORMATS:
                client.get_candles("AAPL", interval=fmt)
                _, kwargs = mock_fetch.call_args
                assert kwargs["interval"].lower() in accepted, f"{fmt!r} -> {kwargs['interval']!r}"
