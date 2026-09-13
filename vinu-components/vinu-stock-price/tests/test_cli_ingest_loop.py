"""Tests for ingest_main's --continuous loop resilience (finding #20):
an unhandled exception from the core sync/backfill/live-cycle calls must
not kill the whole ingest worker process -- it should be logged and the
loop should move on to the next cycle instead.

`vinu_stock.cli` transitively imports `vinu_stock.server.app` ->
`vinu_stock.service` -> the backfill/provider stack, which pulls in
pandas/pyarrow/duckdb. This sandbox's Application Control policy blocks
those native DLLs (same issue documented in test_live_ingest_cycle.py for
pyarrow alone), so -- since these tests only exercise `ingest_main`'s loop
control flow, never real service/app behavior -- `vinu_stock.server.app`
and `vinu_stock.service` are stubbed in `sys.modules` *before* importing
`vinu_stock.cli`, the same technique test_live_ingest_cycle.py uses for
`vinu_stock.storage.parquet`. Any stub this module installs is popped
back out of `sys.modules` immediately after use so other test modules
(e.g. test_events.py, which needs the real `StockService`) still get a
fresh, real import attempt rather than silently inheriting this file's
fake.
"""

from __future__ import annotations

import sys
import types

_STUBBED: list[str] = []


def _stub_if_unimportable(name: str, build_fake) -> None:
    if name in sys.modules:
        return
    try:
        __import__(name)
    except Exception:
        sys.modules[name] = build_fake()
        _STUBBED.append(name)


def _fake_server_app() -> types.ModuleType:
    mod = types.ModuleType("vinu_stock.server.app")
    mod.create_app = lambda *a, **k: None
    return mod


def _fake_service() -> types.ModuleType:
    mod = types.ModuleType("vinu_stock.service")

    class _PlaceholderStockService:  # replaced per-test via @patch
        pass

    mod.StockService = _PlaceholderStockService
    return mod


_stub_if_unimportable("vinu_stock.server.app", _fake_server_app)
_stub_if_unimportable("vinu_stock.service", _fake_service)

from unittest.mock import MagicMock, patch  # noqa: E402

import pytest  # noqa: E402

from vinu_stock.cli import ingest_main  # noqa: E402

# cli.py has already resolved its own module-level `StockService` name
# against the stub above (if one was needed); pop the stub back out so any
# *other* test module that imports vinu_stock.service/server.app fresh
# gets a real (or genuinely-failing) import, not this file's fake.
for _name in _STUBBED:
    sys.modules.pop(_name, None)


@patch("vinu_stock.cli.time.sleep", side_effect=[None, KeyboardInterrupt])
@patch("vinu_stock.cli.StockService")
def test_core_cycle_exception_is_caught_and_loop_continues(mock_service_cls, mock_sleep):
    mock_instance = MagicMock()
    mock_instance.sync_watchlist_from_shared.return_value = {}
    mock_instance.get_pending_backfill_symbols.return_value = []
    # First cycle's run_live_cycle raises; the loop must survive it and
    # reach the second cycle (which triggers the KeyboardInterrupt via
    # the second scripted time.sleep to end the test cleanly).
    mock_instance.run_live_cycle.side_effect = [RuntimeError("boom"), MagicMock(format_report=lambda: "ok")]
    mock_instance.get_settings.return_value.poll_interval_sec = 60
    mock_service_cls.return_value.__enter__.return_value = mock_instance

    with pytest.raises(KeyboardInterrupt):
        ingest_main(["--interval", "60"])

    # run_live_cycle was called twice: the first (failing) cycle didn't
    # abort the loop before a second cycle was attempted.
    assert mock_instance.run_live_cycle.call_count == 2
    assert mock_sleep.call_count == 2


@patch("vinu_stock.cli.time.sleep", side_effect=KeyboardInterrupt)
@patch("vinu_stock.cli.StockService")
def test_refresh_events_still_runs_after_core_cycle_exception(mock_service_cls, mock_sleep):
    mock_instance = MagicMock()
    mock_instance.sync_watchlist_from_shared.side_effect = RuntimeError("watchlist sync boom")
    mock_instance.get_settings.return_value.poll_interval_sec = 60
    mock_instance.refresh_events.return_value = {}
    mock_service_cls.return_value.__enter__.return_value = mock_instance

    with pytest.raises(KeyboardInterrupt):
        ingest_main(["--interval", "60"])

    # The auxiliary refresh_events call is unaffected by the core-cycle
    # failure -- it's still invoked exactly once before sleeping.
    mock_instance.refresh_events.assert_called_once()
