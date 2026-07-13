"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from vinu_features.config import VinuFeaturesConfig
from vinu_features.storage.sqlite_backend import SqliteBackend


class MockCandleClient:
    def fetch_candles(
        self,
        symbol: str,
        *,
        interval: str,
        from_ts: int | None = None,
        to_ts: int | None = None,
        limit: int = 50000,
    ) -> list[dict[str, Any]]:
        ts = from_ts or 1_700_000_000
        end = to_ts or ts + 86400 * 120
        rows: list[dict[str, Any]] = []
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


@pytest.fixture
def tmp_data_dir(tmp_path: Path) -> Path:
    data = tmp_path / "data"
    data.mkdir()
    return data


@pytest.fixture
def backend(tmp_path: Path) -> SqliteBackend:
    db = tmp_path / "meta.db"
    storage = SqliteBackend(db)
    yield storage
    storage.close()


@pytest.fixture
def config(tmp_data_dir: Path, tmp_path: Path) -> VinuFeaturesConfig:
    return VinuFeaturesConfig(
        data_dir=tmp_data_dir,
        meta_db_path=tmp_path / "meta.db",
        stock_api_url="http://test-stock",
        host="127.0.0.1",
        port=8082,
    )
