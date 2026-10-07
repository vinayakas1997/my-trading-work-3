"""API tests with fixture parquet data."""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from vinu_stock.query.cache import get_cache
from vinu_stock.query.engine import invalidate_symbol_cache
from vinu_stock.server.app import create_app
from vinu_stock.service import StockService
from vinu_stock.storage.models import BarRecord
from vinu_stock.storage import parquet
from vinu_stock.storage.paths import archive_year_path


@pytest.fixture(autouse=True)
def _reset_query_caches() -> None:
    # query/engine.py's frame cache (keyed by symbol only, with a 30s
    # cooldown before it even re-checks the file signature) and
    # query/cache.py's indicator cache are both process-wide module
    # singletons -- every test in this file reuses symbol "AAPL" under a
    # fresh tmp_path, so without this a later test can silently read an
    # earlier test's cached frame/indicator result instead of its own.
    # Existing tests never caught this because their assertions (bar
    # count, header presence) happened to be shape-invariant across
    # fixtures; the new gap-count/cache-age tests are the first ones
    # sensitive to which exact data actually came back.
    invalidate_symbol_cache(None)
    get_cache().invalidate(None)
    yield
    invalidate_symbol_cache(None)
    get_cache().invalidate(None)


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    data_root = tmp_path / "data"
    os.environ["VINU_STOCK_DATA_ROOT"] = str(data_root)
    # The real .env sets VINU_SHARED_WATCHLIST_PATH to the Docker-mounted
    # /shared/watchlist.json, not writable on a dev machine -- add_watchlist_
    # tickers() below exports there unconditionally when set, so it must be
    # redirected to a tmp path here.
    os.environ["VINU_SHARED_WATCHLIST_PATH"] = str(tmp_path / "shared_watchlist.json")

    # Seed parquet with recent timestamps aligned to 5m buckets
    now = int(time.time())
    base_ts = (now // 300) * 300 - 10 * 60
    bars = [
        BarRecord("AAPL", "test", base_ts + i * 60, 100 + i, 101 + i, 99 + i, 100 + i, 1000)
        for i in range(10)
    ]
    out = archive_year_path(data_root, "AAPL", 2024)
    parquet.write_bars(out, parquet.bars_to_table(bars))

    service = StockService()
    service._backend.catalog.upsert_symbol(
        "AAPL",
        provider="test",
        first_bar_ts=bars[0].bar_ts,
        last_bar_ts=bars[-1].bar_ts,
        backfill_status="complete",
    )
    service.add_watchlist_tickers(["AAPL"])

    app = create_app(service)
    yield TestClient(app)
    service.close()


def test_health(client: TestClient) -> None:
    resp = client.get("/stock/health")
    assert resp.status_code == 200
    assert resp.json()["symbol_count"] >= 1


def test_candles_1m(client: TestClient) -> None:
    resp = client.get("/stock/candles/AAPL?days=30&limit=100")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 10


def test_candles_5m_aggregate(client: TestClient) -> None:
    resp = client.get("/stock/candles/AAPL?interval=5m&days=30")
    assert resp.status_code == 200
    assert resp.json()["count"] == 2


class TestCandlesAsOfClamp:
    """item #19 finding #1 / item #21 pattern #1: server-side as-of
    enforcement used to not exist at all -- point-in-time safety existed
    only because vinu-agent's tool code remembered to clamp client-side,
    with no server-side safety net for a future caller that forgets.
    The 10 seeded bars span roughly base_ts..base_ts+9min (1-min bars)."""

    def _base_ts(self, client: TestClient) -> int:
        resp = client.get("/stock/candles/AAPL?days=30&limit=100")
        rows = resp.json()["data"]
        return min(r["bar_ts"] for r in rows)

    def test_as_of_excludes_bars_after_the_replay_boundary(self, client: TestClient) -> None:
        base_ts = self._base_ts(client)
        as_of = base_ts + 4 * 60  # keeps bars i=0..4 (5 of the 10 seeded)
        resp = client.get(f"/stock/candles/AAPL?days=30&limit=100&as_of={as_of}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 5
        assert all(r["bar_ts"] <= as_of for r in body["data"])
        assert resp.headers.get("X-Clamped-To-As-Of") == "true"

    def test_explicit_to_beyond_as_of_is_also_clamped(self, client: TestClient) -> None:
        base_ts = self._base_ts(client)
        as_of = base_ts + 4 * 60
        far_future_to = as_of + 10_000
        resp = client.get(
            f"/stock/candles/AAPL?days=30&limit=100&to={far_future_to}&as_of={as_of}",
        )
        assert resp.status_code == 200
        body = resp.json()
        assert all(r["bar_ts"] <= as_of for r in body["data"])
        assert resp.headers.get("X-Clamped-To-As-Of") == "true"

    def test_no_as_of_never_clamps_and_sets_no_header(self, client: TestClient) -> None:
        resp = client.get("/stock/candles/AAPL?days=30&limit=100")
        assert resp.status_code == 200
        assert resp.json()["count"] == 10
        assert "X-Clamped-To-As-Of" not in resp.headers

    def test_as_of_beyond_all_data_is_a_no_op(self, client: TestClient) -> None:
        base_ts = self._base_ts(client)
        resp = client.get(f"/stock/candles/AAPL?days=30&limit=100&as_of={base_ts + 100_000}")
        assert resp.status_code == 200
        assert resp.json()["count"] == 10


def _client_with_bars(tmp_path: Path, bars: list[BarRecord]) -> TestClient:
    data_root = tmp_path / "data"
    os.environ["VINU_STOCK_DATA_ROOT"] = str(data_root)
    os.environ["VINU_SHARED_WATCHLIST_PATH"] = str(tmp_path / "shared_watchlist.json")
    out = archive_year_path(data_root, "AAPL", 2024)
    parquet.write_bars(out, parquet.bars_to_table(bars))
    service = StockService()
    service._backend.catalog.upsert_symbol(
        "AAPL", provider="test", first_bar_ts=bars[0].bar_ts,
        last_bar_ts=bars[-1].bar_ts, backfill_status="complete",
    )
    service.add_watchlist_tickers(["AAPL"])
    return TestClient(create_app(service))


class TestCandlesSessionGapHeader:
    """item #19 finding #2: count_session_gaps() used to run only during
    backfill (backfill/year_job.py) -- a mid-range gap on the live read
    path looked identical to "the market was closed that day." Fixed
    timestamps anchored to a known regular NYSE session (2024-06-03 9:30
    ET, the same anchor test_gap_validation.py's own unit tests use), not
    `now`-relative like the module fixture above, since gap detection
    depends on real session-hours math."""

    _BASE = 1_717_421_400  # 2024-06-03 13:30 UTC = 9:30 ET (session open)

    def test_a_missing_minute_sets_the_gap_count_header(self, tmp_path: Path) -> None:
        bars = [
            BarRecord("AAPL", "test", self._BASE, 100, 101, 99, 100, 1000),
            # skip self._BASE + 60 -- a real 1-minute gap during the session
            BarRecord("AAPL", "test", self._BASE + 120, 100, 101, 99, 100, 1000),
        ]
        client = _client_with_bars(tmp_path, bars)
        resp = client.get(f"/stock/candles/AAPL?from={self._BASE}&to={self._BASE + 200}")
        assert resp.status_code == 200
        assert resp.headers.get("X-Session-Gap-Count") == "1"

    def test_consecutive_bars_set_no_gap_header(self, tmp_path: Path) -> None:
        bars = [
            BarRecord("AAPL", "test", self._BASE + i * 60, 100, 101, 99, 100, 1000)
            for i in range(5)
        ]
        client = _client_with_bars(tmp_path, bars)
        resp = client.get(f"/stock/candles/AAPL?from={self._BASE}&to={self._BASE + 300}")
        assert resp.status_code == 200
        assert "X-Session-Gap-Count" not in resp.headers

    def test_gap_count_not_computed_for_non_1m_intervals(self, tmp_path: Path) -> None:
        # count_session_gaps' own BAR_SEC=60 assumption only means
        # something for 1m bars -- not generalized to other intervals.
        bars = [
            BarRecord("AAPL", "test", self._BASE, 100, 101, 99, 100, 1000),
            BarRecord("AAPL", "test", self._BASE + 120, 100, 101, 99, 100, 1000),
        ]
        client = _client_with_bars(tmp_path, bars)
        resp = client.get(f"/stock/candles/AAPL?interval=5m&from={self._BASE}&to={self._BASE + 200}")
        assert resp.status_code == 200
        assert "X-Session-Gap-Count" not in resp.headers


class TestCandlesCacheAgeHeader:
    """item #19 finding #5: the indicator query-cache's 300s TTL meant a
    "live" caller polling an open-ended window could get stale data with
    no way to tell it was stale."""

    def test_a_cache_hit_reports_its_age(self, client: TestClient) -> None:
        # Explicit from/to, not `days` -- `days` resolves to `now()` on
        # every call, so two back-to-back requests would build two
        # different cache keys and never hit, regardless of this fix.
        base_ts = min(
            r["bar_ts"] for r in client.get("/stock/candles/AAPL?days=30&limit=100").json()["data"]
        )
        url = f"/stock/candles/AAPL?from={base_ts}&to={base_ts + 600}&indicators=sma_5"

        first = client.get(url)
        assert first.status_code == 200
        assert "X-Cache-Age-Seconds" not in first.headers  # first call is a miss

        second = client.get(url)
        assert second.status_code == 200
        assert "X-Cache-Age-Seconds" in second.headers
        assert int(second.headers["X-Cache-Age-Seconds"]) >= 0

    def test_no_indicators_requested_never_sets_the_header(self, client: TestClient) -> None:
        resp = client.get("/stock/candles/AAPL?days=30&limit=100")
        assert resp.status_code == 200
        assert "X-Cache-Age-Seconds" not in resp.headers


def test_catalog(client: TestClient) -> None:
    resp = client.get("/stock/catalog/AAPL")
    assert resp.status_code == 200
    assert resp.json()["data"][0]["symbol"] == "AAPL"


def test_catalog_fallbacks_route_is_registered_before_symbol_route(client: TestClient) -> None:
    """/catalog/fallbacks must not be swallowed by /catalog/{symbol} -- see
    the foundation-fixes audit in missing-pieces-of-system/narating-agents/."""
    resp = client.get("/stock/catalog/fallbacks")
    assert resp.status_code == 200
    assert resp.json() == {"count": 0, "data": []}


def test_backfill_runs_route_empty_by_default(client: TestClient) -> None:
    resp = client.get("/stock/backfill/runs")
    assert resp.status_code == 200
    assert resp.json() == {"count": 0, "data": []}


def test_ui_page(client: TestClient) -> None:
    resp = client.get("/ui/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")
    assert "vinu-stock-price" in resp.text


def test_health_providers(client: TestClient) -> None:
    resp = client.get("/stock/health")
    assert resp.status_code == 200
    body = resp.json()
    assert "providers" in body
    assert isinstance(body["providers"], list)
    assert len(body["providers"]) >= 1


def test_quote_route_unconfigured_is_200_not_ok(client: TestClient) -> None:
    # how-to-make-it-live.md #13: the quote route always returns 200 -- on any
    # upstream problem (here: no Alpaca key in the test env) the body carries
    # ok:false + error, and vinu-live's spread gate fails open on that.
    resp = client.get("/stock/quote/AAPL")
    assert resp.status_code == 200
    body = resp.json()
    assert body["symbol"] == "AAPL"
    assert body["ok"] is False
    assert body["error"]
    assert body["spread_bps"] == 0.0


def test_quote_route_serves_provider_payload_and_caches(client, monkeypatch) -> None:
    from vinu_stock.providers.quote import QuoteResult

    calls = {"n": 0}

    def _fake_get_quote(self, symbol: str) -> QuoteResult:
        calls["n"] += 1
        return QuoteResult(
            True, symbol.upper(), bid=149.98, ask=150.02, mid=150.0,
            spread_bps=2.6667, ts=1_700_000_000.0,
        )

    monkeypatch.setattr(
        "vinu_stock.providers.quote.AlpacaQuoteProvider.get_quote", _fake_get_quote
    )

    first = client.get("/stock/quote/AAPL").json()
    assert first["ok"] is True
    assert first["bid"] == 149.98 and first["ask"] == 150.02
    assert abs(first["spread_bps"] - 2.6667) < 1e-6

    # second call inside the 5s TTL must not hit the provider again
    client.get("/stock/quote/AAPL")
    assert calls["n"] == 1


# ---- quote spreads by session (problem log O10) ----------------------------------------------------------------------------

def _fake_quote(monkeypatch, spread):
    from vinu_stock.providers.quote import QuoteResult

    monkeypatch.setattr(
        "vinu_stock.providers.quote.AlpacaQuoteProvider.get_quote",
        lambda self, symbol: QuoteResult(True, symbol.upper(), bid=99.9, ask=100.1, mid=100.0, spread_bps=spread, ts=time.time()),
    )


def test_a_snapshot_pass_files_the_spread_under_the_current_session_and_the_route_reports_it(client, monkeypatch) -> None:
    _fake_quote(monkeypatch, 4.0)
    service = client.app.state.service if hasattr(client.app.state, "service") else None
    assert client.get("/stock/spread-stats").json()["stats"]["regular"]["snapshots"] == 0
    from vinu_stock.server.routes_read import get_service

    assert get_service().snapshot_spreads() == 1                      # the one watchlist symbol
    body = client.get("/stock/spread-stats?days=1").json()
    assert sum(v["snapshots"] for v in body["stats"].values()) == 1
    assert body["suggested_multipliers"]["regular"] is None           # one snapshot is not enough to suggest anything


def test_an_unusable_quote_is_not_filed(client, monkeypatch) -> None:
    from vinu_stock.providers.quote import QuoteResult
    from vinu_stock.server.routes_read import get_service

    monkeypatch.setattr("vinu_stock.providers.quote.AlpacaQuoteProvider.get_quote",
                        lambda self, symbol: QuoteResult(False, symbol.upper(), error="no quote"))
    assert get_service().snapshot_spreads() == 0


def test_suggested_multipliers_are_session_median_over_regular_median_only_with_enough_samples(tmp_path) -> None:
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from vinu_stock.quotes.spread_store import MIN_SAMPLES, SpreadStore

    ny = ZoneInfo("America/New_York")
    store = SpreadStore(str(tmp_path / "spreads.db"))
    base = datetime(2026, 10, 7, tzinfo=ny)
    for i in range(MIN_SAMPLES):
        store.record("SPY", {"ok": True, "spread_bps": 2.0}, now=base.replace(hour=11, minute=i).timestamp())     # regular
        store.record("SPY", {"ok": True, "spread_bps": 7.0}, now=base.replace(hour=22, minute=i).timestamp())     # overnight
    store.record("SPY", {"ok": True, "spread_bps": 9.0}, now=base.replace(hour=6, minute=0).timestamp())         # one pre-market
    m = store.suggested_multipliers(days=3650, now=base.replace(hour=23, minute=59).timestamp())
    assert m["regular"] == 1.0 and m["overnight"] == 3.5 and m["premarket"] is None
    store.close()
