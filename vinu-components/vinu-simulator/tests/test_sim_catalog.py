from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from vinu_simulator.storage.meta import MetaStorage


def test_upsert_catalog_creates_entry():
    with TemporaryDirectory() as tmp:
        db = MetaStorage(Path(tmp) / "meta.db")
        try:
            db.upsert_catalog_entry("AAPL", "momentum", sharpe=1.5, max_dd=0.1, validated=True)
            entry = db.get_catalog_entry("AAPL", "momentum")
            assert entry is not None
            assert entry["symbol"] == "AAPL"
            assert entry["strategy_name"] == "momentum"
            assert entry["run_count"] >= 1
            assert entry["last_sharpe"] == 1.5
            assert entry["last_max_dd"] == 0.1
        finally:
            db.close()


def test_upsert_catalog_increments_run_count():
    with TemporaryDirectory() as tmp:
        db = MetaStorage(Path(tmp) / "meta.db")
        try:
            db.upsert_catalog_entry("AAPL", "momentum", sharpe=1.0)
            db.upsert_catalog_entry("AAPL", "momentum", sharpe=1.5)
            entry = db.get_catalog_entry("AAPL", "momentum")
            assert entry is not None
            assert entry["run_count"] == 2
            assert entry["last_sharpe"] == 1.5
        finally:
            db.close()


def test_get_catalog_entry_without_strategy():
    with TemporaryDirectory() as tmp:
        db = MetaStorage(Path(tmp) / "meta.db")
        try:
            db.upsert_catalog_entry("AAPL", "momentum", sharpe=1.5)
            db.upsert_catalog_entry("AAPL", "mean_reversion", sharpe=0.8)
            entry = db.get_catalog_entry("AAPL")
            assert entry is not None
            assert entry["last_sharpe"] == 0.8
        finally:
            db.close()


def test_get_catalog_entry_missing():
    with TemporaryDirectory() as tmp:
        db = MetaStorage(Path(tmp) / "meta.db")
        try:
            assert db.get_catalog_entry("NONEXISTENT") is None
        finally:
            db.close()


def test_list_catalog():
    with TemporaryDirectory() as tmp:
        db = MetaStorage(Path(tmp) / "meta.db")
        try:
            db.upsert_catalog_entry("AAPL", "momentum", sharpe=1.5)
            db.upsert_catalog_entry("MSFT", "mean_reversion", sharpe=0.8)
            entries = db.list_catalog()
            assert len(entries) >= 2
        finally:
            db.close()
