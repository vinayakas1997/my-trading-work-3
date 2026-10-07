"""A long intraday window was silently cut to its oldest `limit` bars (15-minute bars for 2024 ended in October, with
`count: 5000` and nothing to say so), so backtests ran on a fraction of the history they asked for. The response now
says when it truncated and where to resume."""
from __future__ import annotations

from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from vinu_stock.server import routes_read

BARS = [{"bar_ts": 1000 + i * 900, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1.0, "adj_factor": 1.0}
        for i in range(10)]


class _Service:
    """Honours `limit` the way the engine does: forward from an explicit start keeps the oldest, open-ended the newest."""

    def get_candles(self, symbol, *, interval, from_ts, to_ts, days, provider, limit, indicators, adjusted, cache_info,
                    closed_only, sessions=None):
        rows = [b for b in BARS if (from_ts is None or b["bar_ts"] >= from_ts)]
        return rows[:limit] if from_ts is not None else rows[-limit:]


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(routes_read.router)
    return TestClient(app)


def _get(**params):
    with patch.object(routes_read, "get_service", return_value=_Service()):
        return _client().get("/candles/X", params={"interval": "15m", **params})


def test_a_window_that_fits_is_not_flagged():
    r = _get(**{"from": 1000, "limit": 10})
    body = r.json()
    assert body["count"] == 10 and body["truncated"] is False and body["next_from"] is None
    assert "x-truncated" not in r.headers


def test_a_cut_window_says_so_and_where_to_resume():
    r = _get(**{"from": 1000, "limit": 4})
    body = r.json()
    assert body["count"] == 4 and body["truncated"] is True
    assert body["next_from"] == body["data"][-1]["bar_ts"] + 1
    assert r.headers["x-truncated"] == "true"


def test_following_next_from_collects_every_bar_once():
    collected, start = [], 1000
    for _ in range(10):
        body = _get(**{"from": start, "limit": 4}).json()
        collected += [b["bar_ts"] for b in body["data"]]
        if not body["truncated"]:
            break
        start = body["next_from"]
    assert collected == [b["bar_ts"] for b in BARS]


def test_an_open_ended_request_keeps_the_newest_bars_and_flags_the_cut():
    body = _get(limit=3).json()
    assert [b["bar_ts"] for b in body["data"]] == [b["bar_ts"] for b in BARS[-3:]]
    assert body["truncated"] is True
