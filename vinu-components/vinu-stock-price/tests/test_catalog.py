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


class TestProviderFallbackLog:
    """A later provider succeeding after an earlier one failed used to be
    absorbed silently into the winning result -- see the foundation-fixes
    audit in missing-pieces-of-system/narating-agents/."""

    def test_record_and_list_round_trip(self, tmp_path: Path) -> None:
        conn = open_catalog_db(tmp_path / "meta.db")
        store = CatalogStore(conn)
        store.init_schema(_SCHEMA)

        store.record_fallback(
            "aapl", role="backfill", winning_provider="polygon",
            skipped_errors=["alpaca: not configured"],
        )
        rows = store.list_recent_fallbacks()
        assert len(rows) == 1
        assert rows[0]["symbol"] == "AAPL"
        assert rows[0]["winning_provider"] == "polygon"
        assert rows[0]["skipped_errors"] == ["alpaca: not configured"]
        conn.close()

    def test_filters_by_symbol(self, tmp_path: Path) -> None:
        conn = open_catalog_db(tmp_path / "meta.db")
        store = CatalogStore(conn)
        store.init_schema(_SCHEMA)

        store.record_fallback("AAPL", role="backfill", winning_provider="yahoo", skipped_errors=["x"])
        store.record_fallback("MSFT", role="backfill", winning_provider="yahoo", skipped_errors=["y"])

        rows = store.list_recent_fallbacks("AAPL")
        assert len(rows) == 1
        assert rows[0]["symbol"] == "AAPL"
        conn.close()

    def test_empty_store_returns_empty_list(self, tmp_path: Path) -> None:
        conn = open_catalog_db(tmp_path / "meta.db")
        store = CatalogStore(conn)
        store.init_schema(_SCHEMA)
        assert store.list_recent_fallbacks() == []
        conn.close()


class TestBackfillRunLog:
    """The aggregate run summary used to be printed once and lost -- see
    the foundation-fixes audit in missing-pieces-of-system/narating-agents/."""

    def test_record_and_list_round_trip(self, tmp_path: Path) -> None:
        conn = open_catalog_db(tmp_path / "meta.db")
        store = CatalogStore(conn)
        store.init_schema(_SCHEMA)

        store.record_backfill_run(
            symbols=["AAPL", "MSFT"], years_attempted=2, years_ok=1, years_failed=1,
            total_rows=500, symbols_skipped=0, rows_rolled=10, errors=["MSFT/2023: timeout"],
        )
        runs = store.list_recent_backfill_runs()
        assert len(runs) == 1
        assert runs[0]["symbols"] == ["AAPL", "MSFT"]
        assert runs[0]["years_failed"] == 1
        assert runs[0]["errors"] == ["MSFT/2023: timeout"]
        conn.close()

    def test_empty_store_returns_empty_list(self, tmp_path: Path) -> None:
        conn = open_catalog_db(tmp_path / "meta.db")
        store = CatalogStore(conn)
        store.init_schema(_SCHEMA)
        assert store.list_recent_backfill_runs() == []
        conn.close()
