"""Append new closed 1m bars to live parquet."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from vinu_stock.catalog.store import CatalogStore
from vinu_stock.providers.registry import ProviderRegistry
from vinu_stock.storage import parquet
from vinu_stock.storage.models import BarRecord
from vinu_stock.storage.paths import live_year_path

LOG = logging.getLogger(__name__)

OVERLAP_SEC = 180


@dataclass
class LiveIngestSummary:
    symbols_polled: int = 0
    bars_added: int = 0
    symbols_failed: int = 0
    errors: list[str] = field(default_factory=list)

    def format_report(self) -> str:
        lines = [
            f"Symbols polled: {self.symbols_polled}",
            f"Bars added: {self.bars_added}",
            f"Symbols failed: {self.symbols_failed}",
        ]
        for err in self.errors[:10]:
            lines.append(f"  - {err}")
        return "\n".join(lines)


def _filter_closed_bars(bars: list[BarRecord], now_ts: int) -> list[BarRecord]:
    """Keep only bars whose minute has fully closed (bar_ts + 60 <= now)."""
    return [b for b in bars if b.bar_ts + 60 <= now_ts]


def run_live_cycle(
    symbols: list[str],
    *,
    data_root: Path,
    catalog: CatalogStore,
    registry: ProviderRegistry,
) -> LiveIngestSummary:
    summary = LiveIngestSummary()
    now_ts = int(time.time())
    current_year = datetime.now(timezone.utc).year

    for raw in symbols:
        sym = raw.strip().upper()
        if not sym:
            continue
        summary.symbols_polled += 1
        entry = catalog.get_symbol(sym)
        last_ts = entry.last_bar_ts if entry and entry.last_bar_ts else None
        start_ts = (last_ts - OVERLAP_SEC) if last_ts else now_ts - 24 * 3600

        result = registry.fetch_bars_with_fallback(sym, start_ts, now_ts, role="live")
        if not result.success:
            summary.symbols_failed += 1
            summary.errors.append(f"{sym}: {result.error}")
            catalog.log_ingest(sym, bars_added=0, from_ts=start_ts, to_ts=now_ts, ok=False, error=result.error)
            continue

        new_bars = result.bars
        if last_ts is not None:
            new_bars = [b for b in new_bars if b.bar_ts > last_ts - OVERLAP_SEC]
        new_bars = _filter_closed_bars(new_bars, now_ts)

        if not new_bars:
            catalog.log_ingest(sym, bars_added=0, from_ts=start_ts, to_ts=now_ts, ok=True)
            continue

        provider_id = new_bars[0].provider
        live_path = live_year_path(data_root, sym, current_year)
        parquet.append_bars(live_path, new_bars)
        catalog.update_bar_range(sym, new_bars, provider=provider_id, live_file=str(live_path))
        summary.bars_added += len(new_bars)
        catalog.log_ingest(
            sym,
            bars_added=len(new_bars),
            from_ts=min(b.bar_ts for b in new_bars),
            to_ts=max(b.bar_ts for b in new_bars),
            ok=True,
        )

    return summary
