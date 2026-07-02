"""Tests for feature engine and worker."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from vinu_features.engine.engine import FeatureEngine
from vinu_features.service import FeatureService
from vinu_features.storage.models import STATUS_DONE, STATUS_PENDING
from vinu_features.worker.runner import FeatureWorker


class MockCandleClient:
    def fetch_candles(
        self,
        symbol: str,
        *,
        interval: str,
        from_ts: int | None,
        to_ts: int | None,
        limit: int = 50000,
    ) -> list[dict[str, Any]]:
        rows = []
        ts = from_ts or 1_700_000_000
        end = to_ts or ts + 86400 * 120
        while ts <= end:
            price = 100.0 + (ts % 86400) / 86400.0
            rows.append(
                {
                    "ts": ts,
                    "open": price,
                    "high": price + 1,
                    "low": price - 1,
                    "close": price,
                    "volume": 1000,
                }
            )
            ts += 86400
        return rows


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
