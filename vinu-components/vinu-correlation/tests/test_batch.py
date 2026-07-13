from unittest.mock import MagicMock, patch

from vinu_correlation.api import CorrelationAPI


def test_get_batch_empty():
    api = MagicMock(spec=CorrelationAPI)
    api.get_batch = CorrelationAPI.get_batch.__get__(api, CorrelationAPI)
    api.get_story = MagicMock(return_value={"ticker": "AAPL"})
    result = api.get_batch(["AAPL"], from_ts=0, to_ts=1000)
    assert result["count"] == 1
    assert "AAPL" in result["results"]


def test_get_batch_error_isolation():
    api = MagicMock(spec=CorrelationAPI)
    api.get_batch = CorrelationAPI.get_batch.__get__(api, CorrelationAPI)
    api.get_story = MagicMock(side_effect=ValueError("fail"))
    result = api.get_batch(["AAPL", "MSFT"])
    assert result["count"] == 2
    assert "error" in result["results"]["AAPL"]
    assert "error" in result["results"]["MSFT"]


def test_get_batch_multi_symbol():
    api = MagicMock(spec=CorrelationAPI)
    api.get_batch = CorrelationAPI.get_batch.__get__(api, CorrelationAPI)

    def side_effect(sym, from_ts=None, to_ts=None):
        return {"ticker": sym}

    api.get_story = MagicMock(side_effect=side_effect)
    result = api.get_batch(["AAPL", "MSFT", "GOOG"])
    assert result["count"] == 3
    assert result["results"]["AAPL"]["ticker"] == "AAPL"
    assert result["results"]["MSFT"]["ticker"] == "MSFT"
