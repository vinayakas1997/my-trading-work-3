"""Backfill orchestrator: queue and run year jobs per symbol."""

from __future__ import annotations

import concurrent.futures
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from vinu_stock.backfill.year_job import run_year_job
from vinu_stock.catalog.store import CatalogStore
from vinu_stock.providers.registry import ProviderRegistry
from vinu_stock.storage import parquet as parquet_storage
from vinu_stock.storage.paths import archive_year_path, live_dir, live_year_path

LOG = logging.getLogger(__name__)

# Start backfilling from this year onward. Data before this date is skipped
# because market structure stabilised around this point — earlier data may
# have different trading hours, tick sizes, or settlement rules that can
# skew strategy backtests.
MIN_BACKFILL_YEAR = 2022

# When the number of daily shard files for the current year exceeds this
# threshold, consolidate them into a single base file.
SHARD_CONSOLIDATION_THRESHOLD = 30


@dataclass
class BackfillSummary:
    symbols: list[str] = field(default_factory=list)
    years_attempted: int = 0
    years_ok: int = 0
    years_failed: int = 0
    total_rows: int = 0
    symbols_skipped: int = 0
    rows_rolled: int = 0
    errors: list[str] = field(default_factory=list)

    def format_report(self) -> str:
        lines = [
            f"Symbols: {', '.join(self.symbols) or '(none)'}",
            f"Years attempted: {self.years_attempted}",
            f"Years OK: {self.years_ok}",
            f"Years failed: {self.years_failed}",
            f"Total rows written: {self.total_rows}",
        ]
        if self.symbols_skipped:
            lines.append(f"Symbols skipped (already complete): {self.symbols_skipped}")
        if self.rows_rolled:
            lines.append(f"Live rows rolled to archive: {self.rows_rolled}")
        for err in self.errors[:10]:
            lines.append(f"  - {err}")
        return "\n".join(lines)


def _discover_first_year(
    symbol: str,
    registry: ProviderRegistry,
) -> int:
    for provider in registry.for_role("backfill"):
        if not provider.is_configured() and provider.provider_id != "yahoo":
            continue
        earliest = provider.earliest_available(symbol)
        if earliest.success and earliest.earliest_ts:
            year = datetime.fromtimestamp(earliest.earliest_ts, tz=timezone.utc).year
            return max(year, MIN_BACKFILL_YEAR)
    yahoo = registry.get("yahoo")
    if yahoo:
        earliest = yahoo.earliest_available(symbol)
        if earliest.success and earliest.earliest_ts:
            year = datetime.fromtimestamp(earliest.earliest_ts, tz=timezone.utc).year
            return max(year, MIN_BACKFILL_YEAR)
    return max(datetime.now(timezone.utc).year, MIN_BACKFILL_YEAR)


def _backfill_symbol(
    sym: str,
    *,
    data_root: Path,
    catalog: CatalogStore,
    registry: ProviderRegistry,
    from_year: int | None,
    end_year: int,
    summary_lock: threading.Lock,
    summary: BackfillSummary,
) -> None:
    entry = catalog.get_symbol(sym)
    if entry and entry.backfill_status == "complete" and from_year is None:
        with summary_lock:
            summary.symbols_skipped += 1
        LOG.info("Skipping %s — backfill already complete", sym)
        return

    catalog.upsert_symbol(sym, backfill_status="partial")
    if from_year is not None:
        start_year = from_year
    else:
        entry = catalog.get_symbol(sym)
        if entry and entry.first_bar_ts is not None:
            start_year = datetime.fromtimestamp(entry.first_bar_ts, tz=timezone.utc).year
        else:
            start_year = _discover_first_year(sym, registry)
    if start_year > end_year:
        catalog.upsert_symbol(sym, backfill_status="complete")
        return

    for year in range(start_year, end_year + 1):
        existing = catalog.get_job_status(sym, year)
        if existing and existing["status"] == "done":
            with summary_lock:
                summary.symbols_skipped += 1
            continue

        catalog.queue_backfill_job(sym, year)
        catalog.set_job_status(sym, year, "running")
        with summary_lock:
            summary.years_attempted += 1
        ok, rows, provider_id, err = run_year_job(
            sym,
            year,
            data_root=data_root,
            catalog=catalog,
            registry=registry,
        )
        if ok:
            with summary_lock:
                summary.years_ok += 1
                summary.total_rows += rows
            catalog.set_job_status(
                sym, year, "done", provider=provider_id, rows_written=rows
            )
        else:
            with summary_lock:
                summary.years_failed += 1
                summary.errors.append(f"{sym}/{year}: {err}")
            catalog.set_job_status(sym, year, "failed", error=err)

    if summary.years_failed > 0:
        catalog.upsert_symbol(sym, backfill_status="partial")
    else:
        catalog.upsert_symbol(sym, backfill_status="complete")


def _consolidate_current_year(
    sym: str,
    *,
    data_root: Path,
    catalog: CatalogStore,
    current_year: int,
    summary_lock: threading.Lock,
    summary: BackfillSummary,
) -> None:
    """Consolidate daily shards for the current live year when threshold is met."""
    live_path = live_year_path(data_root, sym, current_year)
    if not live_path.parent.is_dir():
        return
    live = live_dir(data_root, sym)
    shard_count = len(sorted(live.glob(f"{current_year}_*.parquet")))
    if shard_count < SHARD_CONSOLIDATION_THRESHOLD:
        return
    rows = parquet_storage.consolidate_live_shards(live_path)
    if rows:
        catalog.upsert_symbol(sym, live_file=str(live_path))
        with summary_lock:
            summary.rows_rolled += rows
        LOG.info("Consolidated %d rows for %s current year shards", rows, sym)


def _rollover_previous_years(
    sym: str,
    *,
    data_root: Path,
    catalog: CatalogStore,
    current_year: int,
    summary_lock: threading.Lock,
    summary: BackfillSummary,
) -> None:
    """Promote completed live years (year < current_year) into archive."""
    live = live_dir(data_root, sym)
    if not live.is_dir():
        return

    seen_years: set[int] = set()
    for live_file in sorted(live.glob("*.parquet")):
        stem = live_file.stem
        year_str = stem.split("_")[0]
        if not year_str.isdigit():
            continue
        year = int(year_str)
        if year in seen_years or year >= current_year:
            continue
        seen_years.add(year)

        rows = parquet_storage.read_bars(live_file)
        if rows:
            archive_path = archive_year_path(data_root, sym, year)
            parquet_storage.write_bars(archive_path, rows, merge=True)
            with summary_lock:
                summary.rows_rolled += len(rows)
            LOG.info("Rolled %d rows for %s year %d to archive", len(rows), sym, year)

        for p in sorted(live.glob(f"{year}_*.parquet")):
            try:
                p.unlink()
            except OSError:
                pass
        try:
            live_file.unlink()
        except OSError:
            pass


def rollover_and_consolidate(
    symbols: list[str],
    *,
    data_root: Path,
    catalog: CatalogStore,
    summary_lock: threading.Lock,
    summary: BackfillSummary,
) -> None:
    """Post-backfill maintenance: rollover past live years, consolidate current.

    1. For each symbol, promote any live files for years < current_year into
       the archive directory (single ``{year}.parquet`` per year).
    2. Consolidate daily shard files for the current live year if the number
       of shards exceeds ``SHARD_CONSOLIDATION_THRESHOLD``.
    """
    current_year = datetime.now(timezone.utc).year
    for sym in symbols:
        _rollover_previous_years(
            sym, data_root=data_root, catalog=catalog,
            current_year=current_year,
            summary_lock=summary_lock, summary=summary,
        )
        _consolidate_current_year(
            sym, data_root=data_root, catalog=catalog,
            current_year=current_year,
            summary_lock=summary_lock, summary=summary,
        )


def run_backfill(
    symbols: list[str],
    *,
    data_root: Path,
    catalog: CatalogStore,
    registry: ProviderRegistry,
    from_year: int | None = None,
    to_year: int | None = None,
) -> BackfillSummary:
    summary = BackfillSummary(symbols=[s.strip().upper() for s in symbols])
    if not summary.symbols:
        return summary

    current_year = datetime.now(timezone.utc).year
    end_year = to_year if to_year is not None else current_year - 1
    if end_year > current_year:
        end_year = current_year

    summary_lock = threading.Lock()
    max_workers = min(len(summary.symbols), 4) if summary.symbols else 1

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(
                _backfill_symbol,
                sym,
                data_root=data_root,
                catalog=catalog,
                registry=registry,
                from_year=from_year,
                end_year=end_year,
                summary_lock=summary_lock,
                summary=summary,
            ): sym
            for sym in summary.symbols
        }
        for future in concurrent.futures.as_completed(futures):
            future.result()

    rollover_and_consolidate(
        summary.symbols,
        data_root=data_root,
        catalog=catalog,
        summary_lock=summary_lock,
        summary=summary,
    )

    return summary