"""Tests for AlpacaProvider.fetch_bars_multi (batched multi-symbol bars)."""

from __future__ import annotations

from vinu_stock.config import VinuStockConfig
from vinu_stock.providers.alpaca import AlpacaProvider


def _config(*, api_key: str = "key", api_secret: str = "secret") -> VinuStockConfig:
    return VinuStockConfig(
        data_root="/tmp/data",
        meta_db_path="/tmp/data/vinu_stock_price.db",
        default_poll_interval_sec=60,
        host="127.0.0.1",
        port=8081,
        default_provider="alpaca",
        polygon_api_key="",
        alpaca_api_key=api_key,
        alpaca_api_secret=api_secret,
        alpaca_data_base_url="https://data.alpaca.markets",
        shared_watchlist_path=None,
        finnhub_api_key="",
        events_macro_enabled=False,
        events_refresh_hours=24.0,
    )


def _bar_row(t: str, price: float) -> dict:
    return {"t": t, "o": price, "h": price, "l": price, "c": price, "v": 100, "n": 1}


class _FakeResp:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def json(self) -> dict:
        return self._payload


def test_fetch_bars_multi_single_call_for_multiple_symbols(monkeypatch):
    calls = []

    def fake_get(url, params=None, headers=None, timeout=None):
        calls.append(params)
        return _FakeResp(
            {
                "bars": {
                    "AAPL": [_bar_row("2023-11-14T22:00:00Z", 100.0)],
                    "MSFT": [_bar_row("2023-11-14T22:00:00Z", 200.0)],
                },
                "next_page_token": None,
            }
        )

    monkeypatch.setattr("vinu_stock.providers.alpaca.http_get_with_retry", fake_get)
    provider = AlpacaProvider(_config())

    results = provider.fetch_bars_multi(["AAPL", "MSFT"], 1_700_000_000, 1_700_100_000)

    assert len(calls) == 1  # one HTTP call for both symbols
    assert calls[0]["symbols"] == "AAPL,MSFT"
    assert results["AAPL"].success is True
    assert results["AAPL"].bars[0].close == 100.0
    assert results["MSFT"].success is True
    assert results["MSFT"].bars[0].close == 200.0


def test_fetch_bars_multi_matches_per_symbol_fetch_bars(monkeypatch):
    """The batched call must produce identical bars to calling fetch_bars()
    once per symbol against the same underlying data."""

    payload_by_symbol = {
        "AAPL": [_bar_row("2023-11-14T22:00:00Z", 100.0), _bar_row("2023-11-14T22:01:00Z", 101.0)],
        "MSFT": [_bar_row("2023-11-14T22:00:00Z", 200.0)],
    }

    def fake_get_single(url, params=None, headers=None, timeout=None):
        sym = params["symbols"]
        return _FakeResp({"bars": {sym: payload_by_symbol[sym]}, "next_page_token": None})

    def fake_get_multi(url, params=None, headers=None, timeout=None):
        syms = params["symbols"].split(",")
        return _FakeResp(
            {"bars": {s: payload_by_symbol[s] for s in syms}, "next_page_token": None}
        )

    provider = AlpacaProvider(_config())

    monkeypatch.setattr("vinu_stock.providers.alpaca.http_get_with_retry", fake_get_single)
    expected_aapl = provider.fetch_bars("AAPL", 1_700_000_000, 1_700_100_000)
    expected_msft = provider.fetch_bars("MSFT", 1_700_000_000, 1_700_100_000)

    monkeypatch.setattr("vinu_stock.providers.alpaca.http_get_with_retry", fake_get_multi)
    batched = provider.fetch_bars_multi(["AAPL", "MSFT"], 1_700_000_000, 1_700_100_000)

    assert batched["AAPL"].bars == expected_aapl.bars
    assert batched["MSFT"].bars == expected_msft.bars


def test_fetch_bars_multi_paginates_across_all_symbols(monkeypatch):
    pages = [
        {
            "bars": {"AAPL": [_bar_row("2023-11-14T22:00:00Z", 100.0)], "MSFT": []},
            "next_page_token": "tok1",
        },
        {
            "bars": {"AAPL": [_bar_row("2023-11-14T22:01:00Z", 101.0)], "MSFT": [_bar_row("2023-11-14T22:01:00Z", 201.0)]},
            "next_page_token": None,
        },
    ]
    calls = {"n": 0}

    def fake_get(url, params=None, headers=None, timeout=None):
        page = pages[calls["n"]]
        calls["n"] += 1
        return _FakeResp(page)

    monkeypatch.setattr("vinu_stock.providers.alpaca.http_get_with_retry", fake_get)
    provider = AlpacaProvider(_config())

    results = provider.fetch_bars_multi(["AAPL", "MSFT"], 1_700_000_000, 1_700_100_000)

    assert calls["n"] == 2
    assert len(results["AAPL"].bars) == 2
    assert len(results["MSFT"].bars) == 1


def test_fetch_bars_multi_not_configured_returns_failure_per_symbol():
    provider = AlpacaProvider(_config(api_key="", api_secret=""))
    results = provider.fetch_bars_multi(["AAPL", "MSFT"], 0, 100)
    assert results["AAPL"].success is False
    assert results["MSFT"].success is False


def test_fetch_bars_multi_chunks_large_symbol_lists(monkeypatch):
    provider = AlpacaProvider(_config())
    provider.MAX_BATCH_SYMBOLS = 2
    symbols = ["A", "B", "C", "D", "E"]
    calls = []

    def fake_get(url, params=None, headers=None, timeout=None):
        chunk = params["symbols"].split(",")
        calls.append(chunk)
        return _FakeResp({"bars": {s: [] for s in chunk}, "next_page_token": None})

    monkeypatch.setattr("vinu_stock.providers.alpaca.http_get_with_retry", fake_get)
    results = provider.fetch_bars_multi(symbols, 0, 100)

    assert len(calls) == 3  # ceil(5/2)
    assert set(results.keys()) == set(symbols)
