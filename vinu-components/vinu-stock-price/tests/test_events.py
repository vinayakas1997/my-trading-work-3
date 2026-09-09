"""Event-risk calendar: store, poller, and the /stock/events route.

how-to-make-it-live.md #2 (Stage 4). No network -- the Finnhub provider is
faked; only the store's SQL and the poller's throttle/fail-open logic are
under test here.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from vinu_stock.events.poller import refresh_calendar
from vinu_stock.events.store import MACRO_SYMBOL, EventRecord, EventsStore


@pytest.fixture
def store(tmp_path: Path) -> EventsStore:
    s = EventsStore(str(tmp_path / "vinu_events.db"))
    yield s
    s.close()


class _FakeProvider:
    """Stands in for FinnhubCalendarProvider. `configured` and the record
    lists are set per-test; `raises` forces a failure path."""

    def __init__(self, *, configured=True, earnings=None, economic=None, raises=False):
        self._configured = configured
        self._earnings = earnings or []
        self._economic = economic or []
        self._raises = raises
        self.earnings_calls = 0
        self.economic_calls = 0

    def is_configured(self) -> bool:
        return self._configured

    def get_earnings(self, symbols, from_epoch, to_epoch):
        self.earnings_calls += 1
        if self._raises:
            raise RuntimeError("finnhub boom")
        return list(self._earnings)

    def get_economic(self, from_epoch, to_epoch):
        self.economic_calls += 1
        if self._raises:
            raise RuntimeError("finnhub boom")
        return list(self._economic)


# --- EventsStore ----------------------------------------------------------------

class TestEventsStore:
    def test_replace_kind_and_upcoming_window(self, store: EventsStore) -> None:
        now = time.time()
        store.replace_kind("earnings", [
            EventRecord("AAPL", "earnings", now + 3600, "AAPL earnings (amc)", 2),
            EventRecord("AAPL", "earnings", now + 30 * 86400, "AAPL earnings next quarter", 2),
        ])

        soon = store.upcoming("AAPL", now, now + 24 * 3600)
        assert len(soon) == 1
        assert soon[0]["title"] == "AAPL earnings (amc)"

        wide = store.upcoming("AAPL", now, now + 60 * 86400)
        assert len(wide) == 2

    def test_macro_events_apply_to_every_symbol(self, store: EventsStore) -> None:
        now = time.time()
        store.replace_kind("economic", [
            EventRecord(MACRO_SYMBOL, "economic", now + 7200, "US macro: FOMC rate decision", 2),
        ])
        for sym in ("AAPL", "MSFT", "TSLA"):
            rows = store.upcoming(sym, now, now + 24 * 3600)
            assert len(rows) == 1
            assert rows[0]["title"].startswith("US macro")

    def test_replace_kind_is_a_full_swap(self, store: EventsStore) -> None:
        now = time.time()
        store.replace_kind("earnings", [
            EventRecord("AAPL", "earnings", now + 3600, "old", 2),
        ])
        store.replace_kind("earnings", [
            EventRecord("MSFT", "earnings", now + 3600, "new", 2),
        ])
        assert store.upcoming("AAPL", now, now + 86400) == []
        assert len(store.upcoming("MSFT", now, now + 86400)) == 1

    def test_replace_kind_does_not_touch_other_kinds(self, store: EventsStore) -> None:
        now = time.time()
        store.replace_kind("economic", [
            EventRecord(MACRO_SYMBOL, "economic", now + 3600, "US macro: CPI", 2),
        ])
        store.replace_kind("earnings", [
            EventRecord("AAPL", "earnings", now + 3600, "AAPL earnings", 2),
        ])
        rows = store.upcoming("AAPL", now, now + 86400)
        assert {r["kind"] for r in rows} == {"economic", "earnings"}

    def test_last_pull_round_trips(self, store: EventsStore) -> None:
        assert store.get_last_pull("earnings") == 0.0
        store.set_last_pull("earnings", 1_700_000_000.0)
        assert store.get_last_pull("earnings") == 1_700_000_000.0


# --- refresh_calendar (poller) ------------------------------------------------

class TestRefreshCalendar:
    def test_pulls_when_stale_and_stamps_last_pull(self, store: EventsStore) -> None:
        now = time.time()
        prov = _FakeProvider(
            earnings=[EventRecord("AAPL", "earnings", now + 3600, "AAPL earnings", 2)],
            economic=[EventRecord(MACRO_SYMBOL, "economic", now + 3600, "US macro: FOMC", 2)],
        )
        result = refresh_calendar(store, prov, ["AAPL"], min_interval_hours=20.0)

        assert set(result["refreshed"]) == {"earnings", "economic"}
        assert prov.earnings_calls == 1 and prov.economic_calls == 1
        assert store.count() == 2
        assert store.get_last_pull("earnings") > 0.0

    def test_skips_when_fresh(self, store: EventsStore) -> None:
        store.set_last_pull("earnings", time.time())
        store.set_last_pull("economic", time.time())
        prov = _FakeProvider(earnings=[], economic=[])

        result = refresh_calendar(store, prov, ["AAPL"], min_interval_hours=20.0)

        assert result["refreshed"] == []
        assert prov.earnings_calls == 0 and prov.economic_calls == 0

    def test_no_key_is_a_clean_skip(self, store: EventsStore) -> None:
        prov = _FakeProvider(configured=False)
        result = refresh_calendar(store, prov, ["AAPL"])
        assert result["refreshed"] == []
        assert "skipped" in result
        assert prov.earnings_calls == 0

    def test_provider_error_keeps_existing_rows(self, store: EventsStore) -> None:
        now = time.time()
        store.replace_kind("earnings", [
            EventRecord("AAPL", "earnings", now + 3600, "yesterday's row", 2),
        ])
        prov = _FakeProvider(raises=True)

        result = refresh_calendar(store, prov, ["AAPL"], min_interval_hours=20.0)

        assert result["refreshed"] == []
        assert "errors" in result
        # the stale-but-present row survives a failed pull
        assert len(store.upcoming("AAPL", now, now + 86400)) == 1

    def test_macro_disabled_skips_economic_only(self, store: EventsStore) -> None:
        now = time.time()
        prov = _FakeProvider(
            earnings=[EventRecord("AAPL", "earnings", now + 3600, "AAPL earnings", 2)],
            economic=[EventRecord(MACRO_SYMBOL, "economic", now + 3600, "US macro: CPI", 2)],
        )
        result = refresh_calendar(store, prov, ["AAPL"], macro_enabled=False, min_interval_hours=20.0)

        assert result["refreshed"] == ["earnings"]
        assert prov.economic_calls == 0


# --- /stock/events/{symbol} route -------------------------------------------

class TestEventsRoute:
    @pytest.fixture
    def client(self, tmp_path: Path, monkeypatch):
        from fastapi.testclient import TestClient

        from vinu_stock.server.app import create_app
        from vinu_stock.service import StockService

        monkeypatch.setenv("VINU_STOCK_DATA_ROOT", str(tmp_path / "data"))
        monkeypatch.delenv("FINNHUB_API_KEY", raising=False)
        service = StockService()
        yield service, TestClient(create_app(service))
        service.close()

    def test_no_events_is_200_not_blackout(self, client) -> None:
        _service, tc = client
        resp = tc.get("/stock/events/AAPL")
        assert resp.status_code == 200
        body = resp.json()
        assert body["symbol"] == "AAPL"
        assert body["blackout"] is False
        assert body["configured"] is False
        assert body["events"] == []

    def test_seeded_event_in_window_is_blackout(self, client) -> None:
        service, tc = client
        now = time.time()
        service._events_store.replace_kind("earnings", [
            EventRecord("AAPL", "earnings", now + 6 * 3600, "AAPL earnings (amc)", 2),
        ])

        resp = tc.get("/stock/events/AAPL", params={"within_hours": 24})
        assert resp.status_code == 200
        body = resp.json()
        assert body["blackout"] is True
        assert body["events"][0]["title"] == "AAPL earnings (amc)"

    def test_seeded_event_outside_window_is_not_blackout(self, client) -> None:
        service, tc = client
        now = time.time()
        service._events_store.replace_kind("earnings", [
            EventRecord("AAPL", "earnings", now + 10 * 86400, "AAPL earnings (amc)", 2),
        ])

        resp = tc.get("/stock/events/AAPL", params={"within_hours": 24})
        assert resp.json()["blackout"] is False
