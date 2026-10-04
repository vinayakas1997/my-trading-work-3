"""A live-decision strategy may open positions only after research validated its exact rules, and only on the tickers that
passed. Everything else is blocked, including when the verdicts cannot be read (fail closed). Exits are never gated."""

from __future__ import annotations

import asyncio
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock

import pandas as pd
import pytest

from vinu_infra.strategy_fingerprint import fingerprint
from vinu_live.config import LiveConfig
from vinu_live.live_decision import poller as poller_module
from vinu_live.live_decision.poller import CandleClosePoller
from vinu_live.live_decision.storage import LiveDecisionBackend

CONDITIONS = [{"source": "live_indicators", "key": "adx_14", "operator": "gt", "value": 20}]


def _strategy(name="pullback_1h", conditions=CONDITIONS, schedule="1h", universe=("AAPL", "MSFT", "GOOGL")):
    return {"name": name, "schedule": schedule, "universe": list(universe), "must_conditions": conditions,
            "confirmation_conditions": [], "live_decision_max_hold_bars": 20}


def _row(strategy, status="validated", eligible=("AAPL", "MSFT"), fp=None):
    return {"strategy_id": strategy["name"], "status": status,
            "fingerprint": fp or fingerprint(strategy["must_conditions"], strategy["schedule"], 20),
            "detail": {"eligible_tickers": list(eligible)}}


def _resp(body):
    r = MagicMock()
    r.status_code = 200
    r.json.return_value = body
    r.raise_for_status = MagicMock()
    return r


@pytest.fixture
def poller():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    backend = LiveDecisionBackend(path)
    p = CandleClosePoller(LiveConfig(), backend=backend)        # the gate is ON by default
    p._http = MagicMock()
    yield p
    backend.close()
    os.unlink(path)


def _serve(poller, rows):
    poller._http.get = AsyncMock(return_value=_resp({"validations": rows, "count": len(rows)}))


def test_the_gate_is_on_by_default():
    assert LiveConfig().live_decision_require_validated_strategy is True


def test_a_validated_strategy_is_allowed_only_on_the_tickers_that_passed(poller):
    s = _strategy()
    _serve(poller, [_row(s)])
    assert asyncio.run(poller._validated_tickers([s])) == {"pullback_1h": {"AAPL", "MSFT"}}


@pytest.mark.parametrize("make_row,why", [
    (lambda s: None, "never validated"),
    (lambda s: _row(s, status="rejected"), "rejected"),
    (lambda s: _row(s, status="unvalidatable"), "unvalidatable"),
    (lambda s: _row(s, status="running"), "running"),
    (lambda s: _row(s, fp="0123456789abcdef"), "rules changed"),
])
def test_everything_but_a_current_validation_is_blocked_with_a_reason(poller, caplog, make_row, why):
    import logging
    s = _strategy()
    row = make_row(s)
    _serve(poller, [row] if row else [])
    with caplog.at_level(logging.INFO):
        allowed = asyncio.run(poller._validated_tickers([s]))
    assert allowed == {}
    assert any("blocked from new entries" in r.getMessage() and why in r.getMessage() for r in caplog.records)


def test_editing_a_validated_strategys_rules_cancels_its_approval(poller):
    s = _strategy()
    _serve(poller, [_row(s)])
    edited = _strategy(conditions=[{**CONDITIONS[0], "value": 5}])      # same name, looser rule
    assert asyncio.run(poller._validated_tickers([edited])) == {}


def test_changing_the_bar_size_cancels_its_approval(poller):
    s = _strategy()
    _serve(poller, [_row(s)])
    assert asyncio.run(poller._validated_tickers([_strategy(schedule="15m")])) == {}


def test_unreadable_verdicts_block_every_new_entry(poller):
    poller._http.get = AsyncMock(side_effect=RuntimeError("research is down"))
    assert asyncio.run(poller._validated_tickers([_strategy()])) == {}


def test_a_strategy_without_trigger_conditions_is_not_gated_it_cannot_open_anything(poller):
    _serve(poller, [])
    assert asyncio.run(poller._validated_tickers([_strategy(conditions=[])])) == {}   # not listed as allowed, not logged as blocked


def test_switching_the_gate_off_returns_none(poller):
    poller._config = LiveConfig(live_decision_require_validated_strategy=False)
    assert asyncio.run(poller._validated_tickers([_strategy()])) is None


def test_a_blocked_strategy_is_never_evaluated_and_a_validated_one_only_on_its_tickers(poller, monkeypatch):
    """Full cycle: GOOGL did not pass, so no bars are even fetched for it; with no validation record nothing is fetched."""
    s = _strategy()
    fetched: list[str] = []

    async def fake_fetch(http, url, symbol, interval, limit, closed_only=False):
        fetched.append(symbol)
        return pd.DataFrame()                                       # empty: the cycle skips the pair after the fetch

    monkeypatch.setattr(poller_module, "fetch_recent_bars", fake_fetch)
    poller._fetch_active_strategies = AsyncMock(return_value=[s])
    _serve(poller, [_row(s, eligible=("AAPL", "MSFT"))])
    asyncio.run(poller.cycle())
    assert sorted(fetched) == ["AAPL", "MSFT"]

    fetched.clear()
    _serve(poller, [])                                              # no validation record at all
    asyncio.run(poller.cycle())
    assert fetched == []
