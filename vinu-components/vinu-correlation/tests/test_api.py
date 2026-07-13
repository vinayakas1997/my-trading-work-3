import pytest
from vinu_correlation.api import CorrelationAPI
from vinu_correlation.config import VinuCorrelationConfig
from pathlib import Path
from tempfile import TemporaryDirectory


def _make_test_config(tmp: str) -> VinuCorrelationConfig:
    return VinuCorrelationConfig(
        data_root=Path(tmp),
        news_api_url="http://localhost:18080",
        stock_api_url="http://localhost:18081",
        host="127.0.0.1",
        port=8083,
        impact_high_threshold=2.0,
        impact_medium_threshold=0.5,
        drawdown_min_pct=-3.0,
        drawdown_lookback_hours=24,
        baseline_window_days=7,
        market_hours_only=True,
        session_break_on_close=True,
        cache_maxsize=128,
        cache_ttl_sec=300,
        compute_poll_interval_sec=3600,
        compact_threshold=50,
    )


def test_api_instantiation():
    with TemporaryDirectory() as tmp:
        config = _make_test_config(tmp)
        api = CorrelationAPI(config)
        assert api._config is config
        assert api._cache is not None


@pytest.mark.skip(reason="Requires running vinu-news and vinu-stock-price services")
def test_get_impact_no_news():
    with TemporaryDirectory() as tmp:
        config = _make_test_config(tmp)
        api = CorrelationAPI(config)
        result = api.get_impact("AAPL")
        assert result["event_count"] == 0
        assert result["high_impact_bearish_events"] == 0


@pytest.mark.skip(reason="Requires running vinu-news service")
def test_get_baseline_no_news():
    with TemporaryDirectory() as tmp:
        config = _make_test_config(tmp)
        api = CorrelationAPI(config)
        result = api.get_baseline("AAPL")
        assert result["symbol"] == "AAPL"
        assert "sessions" in result


def test_cache_hits_no_services():
    with TemporaryDirectory() as tmp:
        config = _make_test_config(tmp)
        api = CorrelationAPI(config)
        from unittest.mock import patch
        with patch.object(api._news_client, "get_ticker_news", return_value=[]):
            r1 = api.get_impact("AAPL")
            r2 = api.get_impact("AAPL")
            assert r1 == r2
