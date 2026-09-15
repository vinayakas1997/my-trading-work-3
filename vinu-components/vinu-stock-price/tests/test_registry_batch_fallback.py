"""Tests for ProviderRegistry.fetch_bars_multi_with_fallback (TASK: batch
live-ingest fetches instead of one call per symbol)."""

from __future__ import annotations

from vinu_stock.providers.base import FetchBarsResult
from vinu_stock.providers.registry import ProviderConfig, ProviderRegistry
from vinu_stock.storage.models import BarRecord


class _FakeMultiProvider:
    """A provider that supports batched fetch_bars_multi (like Alpaca)."""

    def __init__(self, provider_id: str, *, configured: bool = True, data: dict | None = None):
        self.provider_id = provider_id
        self._configured = configured
        self._data = data or {}
        self.multi_calls: list[list[str]] = []
        self.single_calls: list[str] = []

    def is_configured(self) -> bool:
        return self._configured

    def fetch_bars_multi(self, symbols, start_ts, end_ts):
        self.multi_calls.append(list(symbols))
        out = {}
        for s in symbols:
            bars = self._data.get(s)
            if bars:
                out[s] = FetchBarsResult(True, bars)
            else:
                out[s] = FetchBarsResult(True, [])
        return out

    def fetch_bars(self, symbol, start_ts, end_ts, *, interval="1m"):
        self.single_calls.append(symbol)
        bars = self._data.get(symbol)
        return FetchBarsResult(True, bars) if bars else FetchBarsResult(True, [])


class _FakeSingleProvider:
    """A provider with no batch capability -- only fetch_bars, like
    Polygon/Yahoo/Tushare today."""

    def __init__(self, provider_id: str, *, configured: bool = True, data: dict | None = None):
        self.provider_id = provider_id
        self._configured = configured
        self._data = data or {}
        self.single_calls: list[str] = []

    def is_configured(self) -> bool:
        return self._configured

    def fetch_bars(self, symbol, start_ts, end_ts, *, interval="1m"):
        self.single_calls.append(symbol)
        bars = self._data.get(symbol)
        return FetchBarsResult(True, bars) if bars else FetchBarsResult(False, [], "empty")


def _bar(sym: str) -> BarRecord:
    return BarRecord(sym, "test", 1_700_000_000, 1, 1, 1, 1, 1)


def test_batches_multi_capable_provider_into_one_call():
    registry = ProviderRegistry()
    alpaca = _FakeMultiProvider("alpaca", data={"AAPL": [_bar("AAPL")], "MSFT": [_bar("MSFT")]})
    registry._providers["alpaca"] = alpaca
    registry._configs = [ProviderConfig("alpaca", True, 1, ("live",))]

    results = registry.fetch_bars_multi_with_fallback(
        ["AAPL", "MSFT"], 0, 100, role="live"
    )

    assert len(alpaca.multi_calls) == 1
    assert set(alpaca.multi_calls[0]) == {"AAPL", "MSFT"}
    assert results["AAPL"].success and results["AAPL"].bars[0].symbol == "AAPL"
    assert results["MSFT"].success and results["MSFT"].bars[0].symbol == "MSFT"


def test_falls_back_to_next_provider_for_symbols_batch_missed():
    registry = ProviderRegistry()
    alpaca = _FakeMultiProvider("alpaca", data={"AAPL": [_bar("AAPL")]})  # MSFT missing
    yahoo = _FakeSingleProvider("yahoo", data={"MSFT": [_bar("MSFT")]})
    registry._providers["alpaca"] = alpaca
    registry._providers["yahoo"] = yahoo
    registry._configs = [
        ProviderConfig("alpaca", True, 1, ("live",)),
        ProviderConfig("yahoo", True, 2, ("live",)),
    ]

    results = registry.fetch_bars_multi_with_fallback(["AAPL", "MSFT"], 0, 100, role="live")

    assert results["AAPL"].bars[0].provider == "test"
    assert yahoo.single_calls == ["MSFT"]  # only the still-missing symbol
    assert results["MSFT"].success


def test_provider_without_batch_support_falls_to_one_call_per_symbol():
    registry = ProviderRegistry()
    provider = _FakeSingleProvider(
        "yahoo", data={"AAPL": [_bar("AAPL")], "MSFT": [_bar("MSFT")]}
    )
    registry._providers["yahoo"] = provider
    registry._configs = [ProviderConfig("yahoo", True, 1, ("live",))]

    results = registry.fetch_bars_multi_with_fallback(["AAPL", "MSFT"], 0, 100, role="live")

    assert sorted(provider.single_calls) == ["AAPL", "MSFT"]
    assert results["AAPL"].success and results["MSFT"].success


def test_unresolved_symbols_return_failure_with_accumulated_errors():
    registry = ProviderRegistry()
    alpaca = _FakeMultiProvider("alpaca", data={})  # never has data
    registry._providers["alpaca"] = alpaca
    registry._configs = [ProviderConfig("alpaca", True, 1, ("live",))]

    results = registry.fetch_bars_multi_with_fallback(["AAPL"], 0, 100, role="live")

    assert results["AAPL"].success is False
    assert "alpaca" in results["AAPL"].error


def test_not_configured_provider_is_skipped_without_calling_it():
    registry = ProviderRegistry()
    alpaca = _FakeMultiProvider("alpaca", configured=False)
    yahoo = _FakeSingleProvider("yahoo", data={"AAPL": [_bar("AAPL")]})
    registry._providers["alpaca"] = alpaca
    registry._providers["yahoo"] = yahoo
    registry._configs = [
        ProviderConfig("alpaca", True, 1, ("live",)),
        ProviderConfig("yahoo", True, 2, ("live",)),
    ]

    results = registry.fetch_bars_multi_with_fallback(["AAPL"], 0, 100, role="live")

    assert alpaca.multi_calls == []
    assert results["AAPL"].success


class _SpyCatalog:
    """Records what would have been persisted -- a real CatalogStore is
    exercised separately in test_catalog.py."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def record_fallback(self, symbol, *, role, winning_provider, skipped_errors):
        self.calls.append({
            "symbol": symbol, "role": role,
            "winning_provider": winning_provider, "skipped_errors": skipped_errors,
        })


class TestFallbackRecording:
    """A later provider succeeding after an earlier one failed used to be
    absorbed silently -- see the foundation-fixes audit in
    missing-pieces-of-system/narating-agents/."""

    def test_records_when_fallback_actually_occurred(self):
        catalog = _SpyCatalog()
        registry = ProviderRegistry(catalog=catalog)
        alpaca = _FakeMultiProvider("alpaca", data={})  # MSFT missing on first try
        yahoo = _FakeSingleProvider("yahoo", data={"MSFT": [_bar("MSFT")]})
        registry._providers["alpaca"] = alpaca
        registry._providers["yahoo"] = yahoo
        registry._configs = [
            ProviderConfig("alpaca", True, 1, ("live",)),
            ProviderConfig("yahoo", True, 2, ("live",)),
        ]

        registry.fetch_bars_multi_with_fallback(["MSFT"], 0, 100, role="live")

        assert len(catalog.calls) == 1
        assert catalog.calls[0]["symbol"] == "MSFT"
        assert catalog.calls[0]["winning_provider"] == "yahoo"
        assert "alpaca" in catalog.calls[0]["skipped_errors"][0]

    def test_no_record_on_clean_first_try_success(self):
        catalog = _SpyCatalog()
        registry = ProviderRegistry(catalog=catalog)
        alpaca = _FakeMultiProvider("alpaca", data={"AAPL": [_bar("AAPL")]})
        registry._providers["alpaca"] = alpaca
        registry._configs = [ProviderConfig("alpaca", True, 1, ("live",))]

        registry.fetch_bars_multi_with_fallback(["AAPL"], 0, 100, role="live")

        assert catalog.calls == []

    def test_no_catalog_is_a_no_op_not_a_crash(self):
        registry = ProviderRegistry()  # catalog=None default
        alpaca = _FakeMultiProvider("alpaca", data={})
        yahoo = _FakeSingleProvider("yahoo", data={"MSFT": [_bar("MSFT")]})
        registry._providers["alpaca"] = alpaca
        registry._providers["yahoo"] = yahoo
        registry._configs = [
            ProviderConfig("alpaca", True, 1, ("live",)),
            ProviderConfig("yahoo", True, 2, ("live",)),
        ]

        results = registry.fetch_bars_multi_with_fallback(["MSFT"], 0, 100, role="live")  # must not raise
        assert results["MSFT"].success

    def test_single_fetch_records_fallback_too(self):
        catalog = _SpyCatalog()
        registry = ProviderRegistry(catalog=catalog)
        alpaca = _FakeSingleProvider("alpaca", data={})  # always empty -> fails
        yahoo = _FakeSingleProvider("yahoo", data={"AAPL": [_bar("AAPL")]})
        registry._providers["alpaca"] = alpaca
        registry._providers["yahoo"] = yahoo
        registry._configs = [
            ProviderConfig("alpaca", True, 1, ("backfill",)),
            ProviderConfig("yahoo", True, 2, ("backfill",)),
        ]

        registry.fetch_bars_with_fallback("AAPL", 0, 100, role="backfill")

        assert len(catalog.calls) == 1
        assert catalog.calls[0]["winning_provider"] == "yahoo"
