"""Catalog store tests."""

from __future__ import annotations

from pathlib import Path

from vinu_stock.catalog.store import CatalogStore, open_catalog_db
from vinu_stock.storage.models import BarRecord

_SCHEMA = (Path(__file__).resolve().parents[1] / "vinu_stock" / "catalog" / "schema.sql").read_text()


def test_catalog_upsert_and_jobs(tmp_path: Path) -> None:
    conn = open_catalog_db(tmp_path / "meta.db")
    store = CatalogStore(conn)
    store.init_schema(_SCHEMA)

    store.upsert_symbol("AAPL", provider="yahoo", backfill_status="pending")
    entry = store.get_symbol("AAPL")
    assert entry is not None
    assert entry.symbol == "AAPL"

    bars = [BarRecord("AAPL", "yahoo", 1000, 1, 2, 0.5, 1.5, 100)]
    store.update_bar_range("AAPL", bars, provider="yahoo")
    entry = store.get_symbol("AAPL")
    assert entry.first_bar_ts == 1000
    assert entry.last_bar_ts == 1000

    store.queue_backfill_job("AAPL", 2024)
    jobs = store.get_pending_jobs()
    assert len(jobs) == 1
    conn.close()
