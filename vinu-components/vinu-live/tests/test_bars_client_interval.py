"""A strategy that says `schedule: daily` must reach the stock service as interval=1d (it answers 'daily' with HTTP 422,
which silently stopped every daily strategy from ever receiving a bar)."""

from __future__ import annotations

import asyncio

import httpx
import pytest

from vinu_live.live_decision.bars_client import fetch_recent_bars, stock_interval


@pytest.mark.parametrize("given,sent", [
    ("daily", "1d"), ("Daily", "1d"), ("1d", "1d"), ("1D", "1d"), ("hourly", "1h"), ("1h", "1h"),
    ("15m", "15m"), ("weekly", "1wk"), ("1wk", "1wk"), (" 5m ", "5m"),
])
def test_interval_words_become_what_the_stock_service_accepts(given, sent):
    assert stock_interval(given) == sent


def test_the_request_carries_the_translated_interval():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["interval"] = request.url.params["interval"]
        return httpx.Response(200, json={"count": 1, "data": [
            {"bar_ts": 1790812800, "open": 1, "high": 2, "low": 0.5, "close": 1.5, "volume": 10}]})

    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            return await fetch_recent_bars(http, "http://stock", "AAPL", "daily", 2, closed_only=True)

    df = asyncio.run(go())
    assert seen["interval"] == "1d" and len(df) == 1
