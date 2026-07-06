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

LOG = logging.getLogger(__name__)


@dataclass
class BackfillSummary:
    symbols: list[str] = field(default_factory=list)
    years_attempted: int = 0
    years_ok: int = 0
    years_failed: int = 0
    total_rows: int = 0
    errors: list[str] = field(default_factory=list)

    def format_report(self) -> str:
        lines = [
            f"Symbols: {', '.join(self.symbols) or '(none)'}",
            f"Years attempted: {self.years_attempted}",
            f"Years OK: {self.years_ok}",
            f"Years failed: {self.years_failed}",
            f"Total rows written: {self.total_rows}",
        ]
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
            return datetime.fromtimestamp(earliest.earliest_ts, tz=timezone.utc).year
    yahoo = registry.get("yahoo")
    if yahoo:
        earliest = yahoo.earliest_available(symbol)
        if earliest.success and earliest.earliest_ts:
            return datetime.fromtimestamp(earliest.earliest_ts, tz=timezone.utc).year
    return datetime.now(timezone.utc).year


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

    catalog.upsert_symbol(sym, backfill_status="complete")


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
        concurrent.futures.wait(futures.keys())

    return summary