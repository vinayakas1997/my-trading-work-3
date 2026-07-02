"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from vinu_features.config import VinuFeaturesConfig
from vinu_features.storage.sqlite_backend import SqliteBackend


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
