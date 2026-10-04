"""Contract: research asks initial-analysis for story / drawdown / correlation over its research window with the query names the
routes really declare (`from_ts`, `to_ts`). With `from` / `to` the routes silently ignored the window, so research got the
whole history, including data after the window it was testing (found by the 2026-10-04 contract scan)."""

from __future__ import annotations

import pytest

from vinu_research.tools import ResearchTools


class _FakeClient:
    def __init__(self):
        self.calls = []

    async def get(self, path, params=None):
        self.calls.append((path, params))
        return {"data": {}}


def _tools():
    t = ResearchTools.__new__(ResearchTools)
    t._correlation_client = _FakeClient()
    return t


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path", [("get_story", "/story/AAPL"), ("get_drawdowns", "/drawdown/AAPL"),
                                         ("get_correlation", "/correlation/AAPL")])
async def test_window_is_sent_as_from_ts_and_to_ts(method, path):
    t = _tools()
    await getattr(t, method)("aapl", 1_700_000_000, 1_710_000_000)
    assert t._correlation_client.calls == [(path, {"from_ts": "1700000000", "to_ts": "1710000000"})]


@pytest.mark.asyncio
async def test_no_window_sends_no_query():
    t = _tools()
    await t.get_story("AAPL", None, None)
    assert t._correlation_client.calls == [("/story/AAPL", {})]
