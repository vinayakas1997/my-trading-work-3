"""Fetch one calendar year of 1m bars into archive parquet."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from vinu_stock.catalog.gap_validation import count_session_gaps
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
    has_adj = 1 if provider_id == "yahoo" and any(b.adj_factor != 1.0 for b in result.bars) else 0
    gap_count = count_session_gaps([b.bar_ts for b in result.bars])
    now = int(datetime.now(timezone.utc).timestamp())
    catalog.upsert_symbol(
        sym,
        provider=provider_id,
        archive_through=str(year),
        backfill_status="partial",
        has_adj_data=has_adj,
        gap_count=gap_count,
        last_validation_at=now,
    )
    if gap_count > 0:
        catalog.log_ingest(
            sym,
            bars_added=row_count,
            from_ts=start_ts,
            to_ts=end_ts,
            ok=True,
            error=f"gap_warning: {gap_count} missing session bars in {year}",
        )
    return True, row_count, provider_id, ""
