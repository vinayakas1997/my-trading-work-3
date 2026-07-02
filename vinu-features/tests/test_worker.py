"""Tests for worker queue."""

from vinu_features.service import FeatureService
from vinu_features.storage.models import STATUS_PENDING


class MockCandleClient:
    def fetch_candles(self, symbol, *, interval, from_ts, to_ts, limit=50000):
        ts = from_ts or 1_700_000_000
        end = to_ts or ts + 86400 * 10
        rows = []
        while ts <= end:
            rows.append(
                {
                    "ts": ts,
                    "open": 100.0,
                    "high": 101.0,
                    "low": 99.0,
                    "close": 100.0,
                    "volume": 1,
                }
            )
            ts += 86400
        return rows


def test_process_pending_limit(config, backend):
    service = FeatureService(config=config, storage=backend, candle_client=MockCandleClient())
    service.submit(title="w1", symbols=["AAPL"], from_ts=1_700_000_000, to_ts=1_700_086_400, preset="basic_ta")
    service.submit(title="w2", symbols=["MSFT"], from_ts=1_700_000_000, to_ts=1_700_086_400, preset="basic_ta")
    results = service.run_worker(once=True, limit=1)
    assert len(results) == 1
    pending = service.list_requests(status=STATUS_PENDING)
    assert len(pending) == 1
    service.close()
