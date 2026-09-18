"""Tests for backfill/year_job.py's shared ticker-profile write --
best-effort, ships inert when shared_root is unset."""

from __future__ import annotations

import sys
import types
from datetime import datetime, timezone
from unittest.mock import MagicMock

if "vinu_stock.storage.parquet" not in sys.modules:
    try:
        import pyarrow  # noqa: F401
    except Exception:
        _fake_parquet = types.ModuleType("vinu_stock.storage.parquet")
        _fake_parquet.write_bars = lambda *a, **k: len(a[1]) if len(a) > 1 else 0
        _fake_parquet.bars_to_table = lambda bars: bars
        sys.modules["vinu_stock.storage.parquet"] = _fake_parquet

from vinu_stock.backfill import year_job  # noqa: E402
from vinu_stock.providers.base import FetchBarsResult  # noqa: E402
from vinu_stock.storage.models import BarRecord  # noqa: E402


def _bar(symbol: str, ts: int) -> BarRecord:
    return BarRecord(
        symbol=symbol, provider="alpaca", bar_ts=ts,
        open=1.0, high=1.0, low=1.0, close=1.0, volume=100.0,
    )


def _fake_registry(bars: list[BarRecord]) -> MagicMock:
    registry = MagicMock()
    registry.fetch_bars_with_fallback.return_value = FetchBarsResult(success=True, bars=bars)
    return registry


class _FakeCatalog:
    def __init__(self) -> None:
        self.upserts: list[tuple[str, dict]] = []

    def update_bar_range(self, *a, **k) -> None:
        pass

    def upsert_symbol(self, sym, **kwargs) -> None:
        self.upserts.append((sym, kwargs))

    def log_ingest(self, *a, **k) -> None:
        pass

    def queue_backfill_job(self, *a, **k) -> None:
        pass


def test_writes_ticker_profile_when_shared_root_set(tmp_path) -> None:
    year = datetime.now(timezone.utc).year
    bars = [_bar("AAPL", int(datetime(year, 1, 3, tzinfo=timezone.utc).timestamp()))]
    shared_root = tmp_path / "shared"

    ok, rows, provider_id, err = year_job.run_year_job(
        "aapl", year,
        data_root=tmp_path, catalog=_FakeCatalog(), registry=_fake_registry(bars),
        shared_root=shared_root,
    )

    assert ok is True
    from vinu_infra.ticker_profile import read_ticker_profile
    profile = read_ticker_profile(shared_root, "AAPL")
    assert profile["vinu_stock_price"]["provider"] == "alpaca"
    assert profile["vinu_stock_price"]["archive_through"] == year
    assert profile["vinu_stock_price"]["gap_count"] == 0


def test_ships_inert_when_shared_root_unset(tmp_path) -> None:
    """No shared_root passed -- identical to calling without the new
    param at all, zero behavior change, and definitely no crash."""
    year = datetime.now(timezone.utc).year
    bars = [_bar("MSFT", int(datetime(year, 1, 3, tzinfo=timezone.utc).timestamp()))]

    ok, rows, provider_id, err = year_job.run_year_job(
        "msft", year,
        data_root=tmp_path, catalog=_FakeCatalog(), registry=_fake_registry(bars),
    )

    assert ok is True
    assert not (tmp_path / "ticker-profiles").exists()
