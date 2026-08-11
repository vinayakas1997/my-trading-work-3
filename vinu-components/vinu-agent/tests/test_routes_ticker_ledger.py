"""Tests for POST /ticker-ledger/event -- Phase 5's cross-container front
door onto TickerLedgerStore (New-talk-agents/new-thinking/new-restructure/
phases/phase-5-monitor-extend/), letting vinu-live write TickerLedger rows
it cannot reach in-process.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import vinu_agent.server.routes_ticker_ledger as routes_ticker_ledger
from vinu_agent.storage.ticker_ledger import TickerLedgerStore


@pytest.fixture
def ticker_ledger_store():
    path = Path(tempfile.mktemp(suffix=".db"))
    store = TickerLedgerStore(path)
    yield store
    store.close()
    try:
        path.unlink(missing_ok=True)
    except PermissionError:
        # TestClient dispatches through its own thread, which can hold a
        # thread-local SQLite connection this fixture's close() (called
        # from the test's own thread) doesn't see -- harmless test-cleanup
        # race on Windows, not a real resource leak (temp dir GC's it).
        pass


@pytest.fixture
def client(ticker_ledger_store):
    fake_service = MagicMock()
    fake_service.ticker_ledger = ticker_ledger_store
    routes_ticker_ledger._get_service = lambda: fake_service
    app = FastAPI()
    app.include_router(routes_ticker_ledger.router)
    return TestClient(app)


def test_add_event_writes_a_real_row(client, ticker_ledger_store) -> None:
    resp = client.post("/ticker-ledger/event", json={
        "ticker": "AAPL", "stage": "monitor", "event_type": "closed_position",
        "text": "position closed", "ref_id": "art_1", "source": "watchlist",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["ticker"] == "AAPL"

    events = ticker_ledger_store.get_events("AAPL")
    assert len(events) == 1
    assert events[0].stage == "monitor"
    assert events[0].event_type == "closed_position"
    assert events[0].ref_id == "art_1"


def test_optional_fields_default(client, ticker_ledger_store) -> None:
    resp = client.post("/ticker-ledger/event", json={
        "ticker": "MSFT", "stage": "monitor", "event_type": "decay_check",
    })
    assert resp.status_code == 200
    events = ticker_ledger_store.get_events("MSFT")
    assert events[0].ref_id == ""
    assert events[0].source == "watchlist"


def test_missing_required_field_is_422(client) -> None:
    resp = client.post("/ticker-ledger/event", json={"ticker": "AAPL"})
    assert resp.status_code == 422
