import pytest
from vinu_initial_analysis.api import CorrelationAPI
from vinu_initial_analysis.config import VinuInitialAnalysisConfig
from pathlib import Path
from tempfile import TemporaryDirectory


def _make_test_config(tmp: str) -> VinuInitialAnalysisConfig:
    return VinuInitialAnalysisConfig(
        data_root=Path(tmp),
        runs_db_path=Path(tmp) / "vinu_initial_analysis_runs.db",
        news_api_url="http://localhost:18080",
        stock_api_url="http://localhost:18081",
        host="127.0.0.1",
        port=8083,
        cache_maxsize=128,
        cache_ttl_sec=300,
        compute_poll_interval_sec=3600,
    )


def test_api_instantiation():
    with TemporaryDirectory() as tmp:
        config = _make_test_config(tmp)
        api = CorrelationAPI(config)
        try:
            assert api._config is config
            assert api._cache is not None
        finally:
            api.close()


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
        try:
            from unittest.mock import patch
            with patch.object(api._news_client, "get_ticker_news", return_value=[]):
                r1 = api.get_impact("AAPL")
                r2 = api.get_impact("AAPL")
                assert r1 == r2
        finally:
            api.close()

