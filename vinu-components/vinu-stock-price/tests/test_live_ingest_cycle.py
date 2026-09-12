"""Tests for run_live_cycle's batched-fetch behavior (TASK: N+1 live-ingest
bar fetches collapsed into one call via registry.fetch_bars_multi_with_fallback).

The key risk with batching per-symbol fetches into one call is that the
individual symbols had different `start_ts` lookback bounds (based on each
symbol's own last-seen bar). A naive batch would fetch from the *earliest*
bound for everyone and could leak extra history into a symbol that should
only see its own, narrower window. These tests pin down that this cannot
happen: each symbol's ingested bars match exactly what the old one-call-per-
symbol path would have produced.
"""

from __future__ import annotations

import sys
import time
import types
from dataclasses import dataclass, field
from pathlib import Path

# vinu_stock.storage.parquet imports pyarrow, which this sandbox's
# Application Control policy blocks from loading (native DLL) -- unrelated
# to the ingest_cycle logic under test here. Stub the module before
# importing ingest_cycle so these tests exercise the batching/filtering
# logic without needing a real pyarrow install; individual tests still
# monkeypatch `ingest_cycle.parquet.append_bars` as needed.
if "vinu_stock.storage.parquet" not in sys.modules:
    try:
        import pyarrow  # noqa: F401
    except Exception:
        _fake_parquet = types.ModuleType("vinu_stock.storage.parquet")
        _fake_parquet.append_bars = lambda path, bars: None
        sys.modules["vinu_stock.storage.parquet"] = _fake_parquet

from vinu_stock.live import ingest_cycle
from vinu_stock.providers.base import FetchBarsResult
from vinu_stock.storage.models import BarRecord


@dataclass
class _Entry:
    symbol: str
    last_bar_ts: int | None


class _FakeCatalog:
    def __init__(self, entries: list[_Entry]):
        self._entries = entries
        self.ingest_log: list[dict] = []
        self.updated: dict[str, list[BarRecord]] = {}

    def list_symbols(self):
        return self._entries

    def log_ingest(self, sym, *, bars_added, from_ts, to_ts, ok, error=None):
        self.ingest_log.append(
            {"symbol": sym, "bars_added": bars_added, "ok": ok, "error": error}
        )

    def update_bar_range(self, sym, bars, *, provider, live_file=None):
        self.updated[sym] = bars


class _FakeBackend:
    def __init__(self, catalog: _FakeCatalog):
        self.catalog = catalog


class _RecordingRegistry:
    """Stands in for ProviderRegistry: records every fetch call so tests can
    assert how many round trips would actually happen, and returns
    pre-scripted bars per symbol."""

    def __init__(self, bars_by_symbol: dict[str, list[BarRecord]]):
        self._bars_by_symbol = bars_by_symbol
        self.multi_calls: list[tuple[list[str], int, int]] = []

    def fetch_bars_multi_with_fallback(self, symbols, start_ts, end_ts, *, role="live"):
        self.multi_calls.append((list(symbols), start_ts, end_ts))
        return {
            sym: FetchBarsResult(True, self._bars_by_symbol.get(sym, []))
            for sym in symbols
        }


def _bar(sym: str, bar_ts: int, close: float = 1.0) -> BarRecord:
    return BarRecord(sym, "alpaca", bar_ts, close, close, close, close, 100)


def test_single_batched_fetch_replaces_one_call_per_symbol(monkeypatch, tmp_path):
    now_ts = int(time.time())
    now_ts -= now_ts % 60  # align to a minute boundary for closed-bar filtering
    now_ts -= 120  # ensure bars up to now-60 are considered closed

    aapl_last = now_ts - 600
    msft_last = now_ts - 3600  # much earlier last-seen bar -> earlier start_ts

    catalog = _FakeCatalog([_Entry("AAPL", aapl_last), _Entry("MSFT", msft_last)])
    backend = _FakeBackend(catalog)

    # For each symbol: one bar well before its own OVERLAP_SEC threshold
    # (must be dropped) and one bar just after last_ts (must survive) --
    # spaced far enough apart to leave no ambiguity about which filter
    # boundary is being exercised.
    bars_by_symbol = {
        "AAPL": [_bar("AAPL", aapl_last - 1000), _bar("AAPL", aapl_last + 60)],
        "MSFT": [_bar("MSFT", msft_last - 1000), _bar("MSFT", msft_last + 60)],
    }
    registry = _RecordingRegistry(bars_by_symbol)

    appended = {}
    monkeypatch.setattr(
        ingest_cycle.parquet, "append_bars", lambda path, bars: appended.setdefault(path, bars)
    )
    monkeypatch.setattr(ingest_cycle.time, "time", lambda: float(now_ts))

    summary = ingest_cycle.run_live_cycle(
        ["AAPL", "MSFT"], data_root=tmp_path, backend=backend, registry=registry
    )

    # Exactly one batched network call for both symbols, not two.
    assert len(registry.multi_calls) == 1
    called_symbols, called_start, called_end = registry.multi_calls[0]
    assert set(called_symbols) == {"AAPL", "MSFT"}
    # The shared start bound is the earliest of the two per-symbol bounds.
    assert called_start == msft_last - ingest_cycle.OVERLAP_SEC
    assert called_end == now_ts

    all_bars = [bar for bars in appended.values() for bar in bars]

    # AAPL: only the bar strictly after (aapl_last - OVERLAP_SEC) survives,
    # exactly as the old per-symbol fetch (which used aapl_last as its own
    # start bound) would have produced -- the far-older bar is dropped even
    # though the shared batched fetch window was wide enough to include it.
    aapl_bars = [b for b in all_bars if b.symbol == "AAPL"]
    assert [b.bar_ts for b in aapl_bars] == [aapl_last + 60]

    msft_bars = [b for b in all_bars if b.symbol == "MSFT"]
    assert [b.bar_ts for b in msft_bars] == [msft_last + 60]

    assert summary.symbols_polled == 2
    assert summary.bars_added == 2
    assert summary.symbols_failed == 0


def test_new_symbol_with_no_watermark_does_not_leak_older_history(monkeypatch, tmp_path):
    """A symbol with no prior last_bar_ts used to get bars bounded only by
    its own `now_ts - 24h` default via the provider's own `start` param.
    Once fetches are batched with a symbol that has a much earlier
    last_bar_ts, the raw fetch result can contain history older than that
    default -- run_live_cycle must still filter it out so behavior is
    unchanged."""
    now_ts = int(time.time())
    now_ts -= now_ts % 60
    now_ts -= 120

    known_last = now_ts - 5 * 86400  # 5 days ago -> pulls the shared start way back
    new_symbol_default_start = now_ts - 24 * 3600

    catalog = _FakeCatalog([_Entry("KNOWN", known_last), _Entry("NEWSYM", None)])
    backend = _FakeBackend(catalog)

    # NEWSYM's raw fetch result (as if the batch call, using KNOWN's earlier
    # start bound, returned history for NEWSYM going back further than
    # NEWSYM's own 24h default window).
    too_old_bar = _bar("NEWSYM", new_symbol_default_start - 3600)
    in_window_bar = _bar("NEWSYM", new_symbol_default_start + 60)
    bars_by_symbol = {
        "KNOWN": [_bar("KNOWN", known_last + 60)],
        "NEWSYM": [too_old_bar, in_window_bar],
    }
    registry = _RecordingRegistry(bars_by_symbol)

    appended = {}
    monkeypatch.setattr(
        ingest_cycle.parquet, "append_bars", lambda path, bars: appended.setdefault(path, bars)
    )
    monkeypatch.setattr(ingest_cycle.time, "time", lambda: float(now_ts))

    ingest_cycle.run_live_cycle(
        ["KNOWN", "NEWSYM"], data_root=tmp_path, backend=backend, registry=registry
    )

    all_bars = [bar for bars in appended.values() for bar in bars]
    newsym_bars = [b for b in all_bars if b.symbol == "NEWSYM"]
    assert too_old_bar not in newsym_bars
    assert in_window_bar in newsym_bars


def test_failed_fetch_marks_symbol_failed(monkeypatch, tmp_path):
    now_ts = int(time.time())
    catalog = _FakeCatalog([_Entry("BAD", None)])
    backend = _FakeBackend(catalog)

    class _FailingRegistry:
        def fetch_bars_multi_with_fallback(self, symbols, start_ts, end_ts, *, role="live"):
            return {s: FetchBarsResult(False, [], "all providers failed") for s in symbols}

    monkeypatch.setattr(ingest_cycle.parquet, "append_bars", lambda path, bars: None)

    summary = ingest_cycle.run_live_cycle(
        ["BAD"], data_root=tmp_path, backend=backend, registry=_FailingRegistry()
    )

    assert summary.symbols_failed == 1
    assert "BAD" in summary.errors[0]
