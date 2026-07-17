"""Tests for feature engine and worker."""

from __future__ import annotations

from pathlib import Path

import pyarrow.parquet as pq

from vinu_tools.engine.engine import FeatureEngine
from vinu_tools.service import FeatureService
from vinu_tools.storage.models import STATUS_DONE, STATUS_PENDING
from vinu_tools.worker.runner import FeatureWorker
from tests.conftest import MockCandleClient


def test_engine_writes_parquet_and_manifest(config, backend):
    engine = FeatureEngine(client=MockCandleClient())
    service = FeatureService(config=config, storage=backend, candle_client=MockCandleClient())
    req = service.submit(
        title="engine_test",
        symbols=["AAPL"],
        from_ts=1_700_000_000,
        to_ts=1_700_086_400,
        preset="basic_ta",
    )
    worker = FeatureWorker(backend, config=config, engine=engine)
    done = worker.process_one(req.id)
    assert done is not None
    assert done.status == STATUS_DONE
    assert done.file_path is not None
    run_dir = Path(done.file_path)
    assert (run_dir / "manifest.md").is_file()
    table = pq.read_table(run_dir / "features.parquet")
    assert "rsi_14" in table.column_names
    service.close()


def test_worker_pending_to_done(config, backend):
    service = FeatureService(config=config, storage=backend, candle_client=MockCandleClient())
    req = service.submit(
        title="worker_test",
        symbols=["AAPL"],
        from_ts=1_700_000_000,
        to_ts=1_700_043_200,
        preset="basic_ta",
    )
    assert req.status == STATUS_PENDING
    results = service.run_worker(once=True, limit=1)
    assert len(results) == 1
    assert results[0].status == STATUS_DONE
    service.close()


def test_dedup_returns_existing_done(config, backend):
    service = FeatureService(config=config, storage=backend, candle_client=MockCandleClient())
    first = service.submit(
        title="dedup_a",
        symbols=["AAPL"],
        from_ts=1_700_000_000,
        to_ts=1_700_043_200,
        preset="basic_ta",
        run_immediately=True,
    )
    second = service.submit(
        title="dedup_b",
        symbols=["AAPL"],
        from_ts=1_700_000_000,
        to_ts=1_700_043_200,
        preset="basic_ta",
    )
    assert first.request_hash == second.request_hash
    assert second.status == STATUS_DONE
    service.close()
