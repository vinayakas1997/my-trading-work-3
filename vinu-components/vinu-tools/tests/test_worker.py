"""Tests for worker queue."""

from vinu_tools.service import FeatureService
from vinu_tools.storage.models import STATUS_PENDING
from tests.conftest import MockCandleClient


def test_process_pending_limit(config, backend):
    service = FeatureService(config=config, storage=backend, candle_client=MockCandleClient())
    service.submit(title="w1", symbols=["AAPL"], from_ts=1_700_000_000, to_ts=1_700_086_400, preset="basic_ta")
    service.submit(title="w2", symbols=["MSFT"], from_ts=1_700_000_000, to_ts=1_700_086_400, preset="basic_ta")
    results = service.run_worker(once=True, limit=1)
    assert len(results) == 1
    pending = service.list_requests(status=STATUS_PENDING)
    assert len(pending) == 1
    service.close()
