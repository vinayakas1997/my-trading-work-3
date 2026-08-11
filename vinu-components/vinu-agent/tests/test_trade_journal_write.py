"""Regression test for a real bug found while building Piece 2
(debrief-on-close): _write_trade_journal_async posted to
`{research_url}/hypotheses`, but that route is actually mounted at
`/research/hypotheses` (vinu_infra/server.py's route_prefix="research",
confirmed by the already-correct CreateHypothesisTool). The mismatch meant
every trade-plan journal write 404'd silently (fire-and-forget, swallowed by
a bare except) — item 3's decision-journal write-side never actually landed
a row in a real run despite passing unit tests that never exercised the URL.

The write now goes through vinu-research's real local HypothesisRegistry
in-process first (see broker/research_link.py), falling back to HTTP only
if that raises -- the HTTP-focused test below forces that fallback the
same way test_trade_plan_calibration.py does.
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from vinu_agent.tools.trade_plan_tool import TradePlanTool
from vinu_research.hypothesis_registry import HypothesisRegistry


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


def _plan_data() -> dict:
    return {
        "symbol": "AAPL",
        "timeframe": "daily",
        "direction": "bullish",
        "trend_stage": "markup",
        "trend_bias": "bullish",
        "entry_rules": [],
        "exit_rules": [],
    }


def _force_in_process_unavailable():
    return patch(
        "vinu_agent.broker.research_link.get_hypothesis_registry",
        side_effect=RuntimeError("not available"),
    )


def test_journal_write_writes_a_real_hypothesis_in_process() -> None:
    registry = HypothesisRegistry(path=Path(tempfile.mktemp(suffix=".json")))
    tool = TradePlanTool()

    with patch("vinu_agent.broker.research_link.get_hypothesis_registry", return_value=registry):
        asyncio.run(tool._write_trade_journal_async("http://research-api:8087", _plan_data()))

    hypotheses = registry.list_all()
    assert len(hypotheses) == 1
    assert hypotheses[0].universe == ["AAPL"]
    assert hypotheses[0].strategy_type == "trade_plan_daily"


def test_journal_write_hits_the_actual_mounted_research_prefix() -> None:
    tool = TradePlanTool()

    with _force_in_process_unavailable():
        with patch("httpx.AsyncClient", _FakeAsyncClient):
            asyncio.run(tool._write_trade_journal_async("http://research-api:8087", _plan_data()))

    assert len(_FakeAsyncClient.calls) == 1
    url, _payload = _FakeAsyncClient.calls[0]
    assert url == "http://research-api:8087/research/hypotheses"
