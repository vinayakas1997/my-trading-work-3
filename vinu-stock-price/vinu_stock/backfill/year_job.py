"""Fetch one calendar year of 1m bars into archive parquet."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from vinu_stock.catalog.store import CatalogStore
from vinu_stock.providers.registry import ProviderRegistry
from vinu_stock.storage import parquet
from vinu_stock.storage.paths import archive_year_path


def run_year_job(
    symbol: str,
    year: int,
    *,
    data_root: Path,
    catalog: CatalogStore,
    registry: ProviderRegistry,
) -> tuple[bool, int, str, str]:
    """Returns (ok, rows_written, provider_id, error)."""
    sym = symbol.strip().upper()
    start_dt = datetime(year, 1, 1, tzinfo=timezone.utc)
    end_dt = datetime(year + 1, 1, 1, tzinfo=timezone.utc) - timedelta(seconds=1)
    now = datetime.now(timezone.utc)
    if start_dt > now:
        return True, 0, "", "future year skipped"
    if end_dt > now:
        end_dt = now

    start_ts = int(start_dt.timestamp())
    end_ts = int(end_dt.timestamp())

    result = registry.fetch_bars_with_fallback(sym, start_ts, end_ts, role="backfill")
    if not result.success or not result.bars:
        return False, 0, "", result.error or "No bars returned"

    provider_id = result.bars[0].provider
    out_path = archive_year_path(data_root, sym, year)
    row_count = parquet.write_bars(out_path, result.bars, merge=True)
    catalog.update_bar_range(sym, result.bars, provider=provider_id)
    catalog.upsert_symbol(
        sym,
        provider=provider_id,
        archive_through=str(year),
        backfill_status="partial",
    )
    return True, row_count, provider_id, ""
