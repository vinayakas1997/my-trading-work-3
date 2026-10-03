"""logic-audit-2026-10-02 A8 (the-inconsistencies-v2, Phase 4): the live feature window is configurable.

`live_decision_feature_window_bars` (0 = old behavior): the poller fetches
max(minimum warmup, configured) bars so slow EMAs converge toward their backtest values.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock

import pytest

from vinu_live.config import LiveConfig
from vinu_live.live_decision.detector import feature_window_bars, min_warmup_bars
from vinu_live.live_decision.poller import CandleClosePoller
from vinu_live.live_decision.storage import LiveDecisionBackend


def test_flag_defaults_to_old_behavior_and_reads_env(monkeypatch):
    assert LiveConfig().live_decision_feature_window_bars == 0
    monkeypatch.setenv("VINU_LIVE_DECISION_FEATURE_WINDOW_BARS", "600")
    assert LiveConfig.from_env().live_decision_feature_window_bars == 600


def test_feature_window_bars_is_never_below_the_minimum():
    m = min_warmup_bars()
    assert feature_window_bars(0) == m
    assert feature_window_bars(None) == m
    assert feature_window_bars(10) == m          # a too-small setting cannot shrink below warmup
    assert feature_window_bars(600) == 600
    assert feature_window_bars(m + 1) == m + 1


def _resp(body):
    r = MagicMock()
    r.status_code = 200
    r.json.return_value = body
    r.raise_for_status = MagicMock()
    return r


def _bars(n, start=1_700_000_000, step=900):
    return {"count": n, "data": [
        {"open": 100.0 + i, "high": 101.0 + i, "low": 99.0 + i, "close": 100.5 + i, "volume": 1000.0,
         "ts": start + i * step} for i in range(n)]}


def _warmup_limit_requested(window_setting: int) -> int:
    """Run one poller cycle and return the `limit` of the big (warmup) candles fetch."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    backend = LiveDecisionBackend(path)
    try:
        p = CandleClosePoller(LiveConfig(live_decision_feature_window_bars=window_setting), backend=backend)
        p._http = MagicMock()
        limits: list[int] = []

        async def _get(url, params=None, **kw):
            if "/strategy/strategies/strat_a" in url:
                return _resp({"name": "strat_a", "schedule": "15m", "universe": ["AAPL"], "must_conditions": [],
                              "confirmation_conditions": [], "grace_window_bars": 5})
            if "/strategy/strategies" in url:
                return _resp([{"name": "strat_a", "enabled": True}])
            if "/stock/candles/AAPL" in url:
                limit = (params or {}).get("limit", 2)
                limits.append(limit)
                return _resp(_bars(min(limit, 800)))
            raise AssertionError(url)

        p._http.get = AsyncMock(side_effect=_get)
        asyncio.run(p.cycle())
        return max(limits)
    finally:
        backend.close()
        if os.path.exists(path):
            os.unlink(path)


def test_poller_default_fetches_the_minimum_window():
    assert _warmup_limit_requested(0) == min_warmup_bars()


@pytest.mark.parametrize("setting", [400, 600])
def test_poller_fetches_the_configured_larger_window(setting):
    assert _warmup_limit_requested(setting) == setting
