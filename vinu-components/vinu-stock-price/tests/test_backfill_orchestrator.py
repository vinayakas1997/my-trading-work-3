"""Tests for backfill/orchestrator.py's run_backfill:

- #25: one symbol raising an unhandled exception (not the normal
  ok/err-tuple failure path `_backfill_symbol` already handles per-year)
  must not crash the whole `run_backfill` call -- it should be logged and
  recorded in `BackfillSummary.errors`, and every other symbol must still
  run to completion.
- #24: `end_year` must default to the *current* year (not
  `current_year - 1`), so the still-accumulating live year is included in
  gap detection, unless the caller passes an explicit `to_year`.

`vinu_stock.backfill.orchestrator` transitively imports
`vinu_stock.storage.parquet` (pyarrow) via `year_job.py`; this sandbox's
Application Control policy blocks that native DLL (documented already in
test_live_ingest_cycle.py), so that module is stubbed the same way here --
these tests never exercise real Parquet I/O, only the orchestration logic.
"""

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
        _fake_parquet.append_bars = lambda path, bars: None
        _fake_parquet.write_bars = lambda *a, **k: 0
        _fake_parquet.read_bars = lambda *a, **k: []
        _fake_parquet.bars_to_table = lambda bars: bars
        _fake_parquet.consolidate_live_shards = lambda *a, **k: 0
        sys.modules["vinu_stock.storage.parquet"] = _fake_parquet

from vinu_stock.backfill import orchestrator  # noqa: E402


class _Entry:
    def __init__(self, backfill_status=None, first_bar_ts=None):
        self.backfill_status = backfill_status
        self.first_bar_ts = first_bar_ts


class _FakeCatalog:
    """Minimal CatalogStore stand-in. `fail_symbols` simulates an
    unexpected crash (e.g. a DB error) for `get_symbol`, exercising the
    "one symbol's exception must not abort the run" path (#25) -- distinct
    from `run_year_job`'s normal (ok, rows, provider, err) failure tuple,
    which `_backfill_symbol` already handles per-year."""

    def __init__(self, fail_symbols: set[str] = frozenset()):
        self.fail_symbols = fail_symbols
        self.job_statuses: dict[tuple[str, int], dict] = {}
        self.upserts: list[tuple[str, dict]] = []
        self.recorded_runs: list[dict] = []

    def get_symbol(self, sym):
        if sym in self.fail_symbols:
            raise RuntimeError(f"catalog lookup boom for {sym}")
        return None

    def upsert_symbol(self, sym, **kwargs):
        self.upserts.append((sym, kwargs))

    def get_job_status(self, sym, year):
        return self.job_statuses.get((sym, year))

    def queue_backfill_job(self, sym, year):
        pass

    def set_job_status(self, sym, year, status, **kwargs):
        self.job_statuses[(sym, year)] = {"status": status, **kwargs}

    def record_backfill_run(self, **kwargs):
        self.recorded_runs.append(kwargs)


class _FakeBackend:
    def __init__(self, catalog: _FakeCatalog):
        self.catalog = catalog


def _no_op_registry() -> MagicMock:
    registry = MagicMock()
    registry.for_role.return_value = []
    registry.get.return_value = None
    return registry


def test_one_symbol_crash_is_recorded_and_others_still_run(monkeypatch, tmp_path):
    catalog = _FakeCatalog(fail_symbols={"BAD"})
    backend = _FakeBackend(catalog)
    registry = _no_op_registry()

    monkeypatch.setattr(
        orchestrator, "run_year_job",
        lambda sym, year, **kw: (True, 42, "yahoo", ""),
    )

    current_year = datetime.now(timezone.utc).year
    summary = orchestrator.run_backfill(
        ["BAD", "GOOD"],
        data_root=tmp_path,
        backend=backend,
        registry=registry,
        to_year=current_year,
    )

    # BAD's crash is recorded, mentioning the symbol...
    assert any("BAD" in e for e in summary.errors)
    # ...but did not stop GOOD from being backfilled.
    assert summary.years_ok >= 1
    assert summary.total_rows == 42


def test_end_year_defaults_to_current_year_not_previous(monkeypatch, tmp_path):
    """#24: a mid-session provider outage in the live year must be
    detectable by gap validation, which requires the live year to actually
    be included in the backfill range by default."""
    captured: dict = {}

    def fake_backfill_symbol(sym, *, data_root, backend, registry, from_year, end_year, summary_lock, summary, **_kw):
        captured["end_year"] = end_year

    monkeypatch.setattr(orchestrator, "_backfill_symbol", fake_backfill_symbol)

    backend = _FakeBackend(_FakeCatalog())
    registry = _no_op_registry()

    orchestrator.run_backfill(["AAPL"], data_root=tmp_path, backend=backend, registry=registry)

    assert captured["end_year"] == datetime.now(timezone.utc).year


def test_explicit_to_year_is_still_respected(monkeypatch, tmp_path):
    captured: dict = {}

    def fake_backfill_symbol(sym, *, data_root, backend, registry, from_year, end_year, summary_lock, summary, **_kw):
        captured["end_year"] = end_year

    monkeypatch.setattr(orchestrator, "_backfill_symbol", fake_backfill_symbol)

    backend = _FakeBackend(_FakeCatalog())
    registry = _no_op_registry()

    orchestrator.run_backfill(
        ["AAPL"], data_root=tmp_path, backend=backend, registry=registry, to_year=2023,
    )

    assert captured["end_year"] == 2023


def test_run_summary_is_persisted_via_catalog(monkeypatch, tmp_path):
    """The aggregate run summary used to be printed/returned once and then
    lost -- see the foundation-fixes audit in
    missing-pieces-of-system/narating-agents/."""
    catalog = _FakeCatalog()
    backend = _FakeBackend(catalog)
    registry = _no_op_registry()

    monkeypatch.setattr(
        orchestrator, "run_year_job",
        lambda sym, year, **kw: (True, 10, "yahoo", ""),
    )

    current_year = datetime.now(timezone.utc).year
    summary = orchestrator.run_backfill(
        ["AAPL"], data_root=tmp_path, backend=backend, registry=registry, to_year=current_year,
    )

    assert len(catalog.recorded_runs) == 1
    recorded = catalog.recorded_runs[0]
    assert recorded["symbols"] == summary.symbols
    assert recorded["total_rows"] == summary.total_rows
    assert recorded["years_failed"] == summary.years_failed


def test_run_summary_persistence_failure_does_not_break_run(monkeypatch, tmp_path):
    class _BoomCatalog(_FakeCatalog):
        def record_backfill_run(self, **kwargs):
            raise RuntimeError("db boom")

    backend = _FakeBackend(_BoomCatalog())
    registry = _no_op_registry()
    monkeypatch.setattr(
        orchestrator, "run_year_job",
        lambda sym, year, **kw: (True, 1, "yahoo", ""),
    )

    summary = orchestrator.run_backfill(  # must not raise
        ["AAPL"], data_root=tmp_path, backend=backend, registry=registry,
        to_year=datetime.now(timezone.utc).year,
    )
    assert summary.years_ok >= 1
