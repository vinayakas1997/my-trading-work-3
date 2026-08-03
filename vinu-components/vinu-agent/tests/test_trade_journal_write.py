"""Regression test for a real bug found while building Piece 2
(debrief-on-close): _write_trade_journal_async posted to
`{research_url}/hypotheses`, but that route is actually mounted at
`/research/hypotheses` (vinu_lib/server.py's route_prefix="research",
confirmed by the already-correct CreateHypothesisTool). The mismatch meant
every trade-plan journal write 404'd silently (fire-and-forget, swallowed by
a bare except) — item 3's decision-journal write-side never actually landed
a row in a real run despite passing unit tests that never exercised the URL."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest

from vinu_agent.tools.trade_plan_tool import TradePlanTool


class _FakeResponse:
    def __init__(self, status_code: int = 200, payload: dict | None = None) -> None:
        self.status_code = status_code
        self._payload = payload or {"hypothesis_id": "hyp_test"}

    def json(self) -> dict:
        return self._payload


class _FakeAsyncClient:
    calls: list[tuple[str, dict]] = []

    def __init__(self, *args, **kwargs) -> None:
        pass

    async def __aenter__(self) -> "_FakeAsyncClient":
        return self

    async def __aexit__(self, *args) -> bool:
        return False

    async def post(self, url: str, json: dict | None = None, **kwargs):
        _FakeAsyncClient.calls.append((url, json or {}))
        return _FakeResponse()


@pytest.fixture(autouse=True)
def _reset_calls():
    _FakeAsyncClient.calls = []
    yield


def test_journal_write_hits_the_actual_mounted_research_prefix() -> None:
    tool = TradePlanTool()
    plan_data = {
        "symbol": "AAPL",
        "timeframe": "daily",
        "direction": "bullish",
        "trend_stage": "markup",
        "trend_bias": "bullish",
        "entry_rules": [],
        "exit_rules": [],
    }
    with patch("httpx.AsyncClient", _FakeAsyncClient):
        asyncio.run(tool._write_trade_journal_async("http://research-api:8087", plan_data))

    assert len(_FakeAsyncClient.calls) == 1
    url, _payload = _FakeAsyncClient.calls[0]
    assert url == "http://research-api:8087/research/hypotheses"
