from datetime import timezone
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from vinu_correlation.config import VinuCorrelationConfig
from vinu_correlation.storage.backend import CorrelationStorage
from vinu_correlation.storage.models import IMPACT_SCHEMA


def test_append_and_read_events():
    with TemporaryDirectory() as tmp:
        config = VinuCorrelationConfig(
            data_root=Path(tmp),
            news_api_url="http://localhost:8080",
            stock_api_url="http://localhost:8081",
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
        storage = CorrelationStorage(config.data_root)

        ts = int(__import__("time").time())
        events = [
            {"article_id": "art_1", "symbol": "AAPL", "is_primary": True,
             "ticker_count": 1, "ts": ts, "session": "regular",
             "headline": "Test", "sentiment": "BULLISH", "sentiment_score": 5,
             "impact_label": "high_bullish", "price_change_5m": 0.5,
             "price_change_15m": 1.0, "price_change_30m": 1.5,
             "price_change_1h": 2.0, "price_change_1d": 3.0,
             "abnormal_return_30m": 0.02, "car_1h": 0.05,
             "ar_p_value": 0.01, "ar_significant": True,
             "thread_id": "", "computed_at": ts},
        ]
        storage.append_events("AAPL", events)

        last_ts = storage.get_last_computed_ts("AAPL")
        assert last_ts == ts

        from datetime import timezone
        year = datetime.fromtimestamp(ts, tz=timezone.utc).year
        table = storage.read_events("AAPL", year)
        assert table is not None
        assert table.num_rows == 1


def test_incremental_append():
    with TemporaryDirectory() as tmp:
        config = VinuCorrelationConfig(
            data_root=Path(tmp),
            news_api_url="http://localhost:8080",
            stock_api_url="http://localhost:8081",
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
        storage = CorrelationStorage(config.data_root)

        def _make_event(article_id, ts):
            return {"article_id": article_id, "symbol": "AAPL", "is_primary": True,
                    "ticker_count": 1, "ts": ts, "session": "regular",
                    "headline": "Test", "sentiment": "NEUTRAL", "sentiment_score": 0,
                    "impact_label": "low", "price_change_5m": 0.0,
                    "price_change_15m": 0.0, "price_change_30m": 0.0,
                    "price_change_1h": 0.0, "price_change_1d": 0.0,
                    "abnormal_return_30m": 0.0, "car_1h": 0.0,
                    "ar_p_value": 1.0, "ar_significant": False,
                    "thread_id": "", "computed_at": ts}

        ts1 = int(__import__("time").time())
        ts2 = ts1 + 3600
        storage.append_events("AAPL", [_make_event("art_1", ts1)])
        assert storage.get_last_computed_ts("AAPL") == ts1

        storage.append_events("AAPL", [_make_event("art_2", ts2)])
        assert storage.get_last_computed_ts("AAPL") == ts2


def test_compact():
    with TemporaryDirectory() as tmp:
        config = VinuCorrelationConfig(
            data_root=Path(tmp),
            news_api_url="http://localhost:8080",
            stock_api_url="http://localhost:8081",
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
        storage = CorrelationStorage(config.data_root)
        storage.compact("AAPL", 2026)
