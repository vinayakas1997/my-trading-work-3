from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pandas as pd
import pytest

from vinu_portfolio.capital_plan import build_capital_plan, edge_stats


def _cfg(**kw):
    base = dict(live_api_url="http://live", capital_min_history=20, capital_kelly_scale=0.25,
                capital_max_position_pct=0.25, capital_fractional_shares=False)
    base.update(kw)
    return SimpleNamespace(**base)


def _http(ledger, status=200):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = ledger
    http = MagicMock()
    http.get = AsyncMock(return_value=resp)
    return http


def _returns(n=60, seed=1):
    rng = np.random.default_rng(seed)
    return pd.Series(rng.normal(0.004, 0.01, n))


def _ledger(committed=0.0, positions=(), mode="real"):
    return {"status": "ok", "account_mode": mode, "capped": True, "committed": committed,
            "open_positions": list(positions), "free_cash": 12.0 - committed, "reserve": 8.0, "reserve_fraction": 0.4, "results": {}}


def _run(ledger, monkeypatch, tilted=None, price=5.0, returns=None, scale=1.0, **cfg):
    monkeypatch.setenv("VINU_ACCOUNT_MODE", "real")
    monkeypatch.setenv("VINU_REAL_CAPITAL", "20")
    tilted = tilted or [{"name": "s1", "symbol": "AAA"}]
    ret = _returns() if returns is None else returns

    async def returns_for(_s):
        return ret

    async def price_for(_sym):
        return price

    return asyncio.run(build_capital_plan(
        http=_http(ledger), config=_cfg(**cfg), tilted=tilted, strategies_by_name={"s1": {"artifact_id": "art_1"}},
        returns_for=returns_for, price_for=price_for, free_cash_scale=scale))


def test_without_a_capital_base_nothing_changes(monkeypatch):
    monkeypatch.delenv("VINU_REAL_CAPITAL", raising=False)
    monkeypatch.setenv("VINU_ACCOUNT_MODE", "paper")
    out = asyncio.run(build_capital_plan(http=_http({}), config=_cfg(), tilted=[], strategies_by_name={},
                                         returns_for=AsyncMock(), price_for=AsyncMock(), free_cash_scale=1.0))
    assert out["status"] == "not_capped"


def test_an_unreadable_ledger_funds_nobody(monkeypatch):
    monkeypatch.setenv("VINU_ACCOUNT_MODE", "real")
    monkeypatch.setenv("VINU_REAL_CAPITAL", "20")
    out = asyncio.run(build_capital_plan(http=_http({}, status=500), config=_cfg(), tilted=[{"name": "s1", "symbol": "AAA"}],
                                         strategies_by_name={}, returns_for=AsyncMock(), price_for=AsyncMock(), free_cash_scale=1.0))
    assert out["status"] == "capital_ledger_unavailable" and "plan" not in out


def test_a_ledger_of_the_other_money_mode_is_refused(monkeypatch):
    out = _run(_ledger(mode="paper"), monkeypatch)
    assert out["status"] == "account_mode_mismatch"


def test_the_plan_is_sized_from_the_twenty_dollars_not_the_account(monkeypatch):
    out = _run(_ledger(), monkeypatch, price=1.0)
    assert out["status"] == "ok" and out["capital_base"] == 20.0
    assert 0 < out["deployable_total"] <= 12.0 + 1e-9            # never more than the free cash
    assert out["deployable_total"] <= 20.0 * 0.25 + 1e-9         # nor above the position cap


def test_committed_money_counts_and_leaves_less_to_spend(monkeypatch):
    held = [{"symbol": "AAA", "cost": 1.76}]
    out = _run(_ledger(committed=1.76, positions=held), monkeypatch, price=1.0)
    assert out["plan"]["free_cash_before"] == pytest.approx(10.24)
    assert out["target_dollars"]["s1"] >= 1.76 - 1e-9            # what it holds is kept in the target


def test_a_strategy_with_too_little_history_is_not_funded_but_keeps_what_it_holds(monkeypatch):
    out = _run(_ledger(committed=1.76, positions=[{"symbol": "AAA", "cost": 1.76}]), monkeypatch,
               returns=_returns(n=5))
    assert out["skipped"][0]["reason"] == "not_enough_history"
    assert out["target_dollars"]["s1"] == pytest.approx(1.76)


def test_a_share_that_costs_more_than_the_free_cash_is_not_bought(monkeypatch):
    out = _run(_ledger(), monkeypatch, price=336.0)
    assert out["target_dollars"]["s1"] == 0 and out["plan"]["refused"][0]["reason"] == "price_above_available_funds"


def test_edge_stats_ignores_flat_periods_and_short_history():
    r = pd.Series([0.01, -0.005, 0.0, 0.02, -0.01] * 8)
    s = edge_stats(r, 20)
    assert s["n"] == 32 and s["p_win"] == pytest.approx(0.5) and s["avg_win"] == pytest.approx(0.015)
    assert edge_stats(r.iloc[:6], 20) is None and edge_stats(None, 20) is None


def test_the_capital_plan_route_shows_the_ledger_even_when_nothing_is_allocated(monkeypatch):
    from unittest.mock import patch
    from fastapi.testclient import TestClient
    from vinu_portfolio.server.app import create_app

    monkeypatch.setenv("VINU_ACCOUNT_MODE", "paper")
    monkeypatch.setenv("VINU_REAL_CAPITAL", "20")
    ledger = {"status": "ok", "free_cash": 12.0, "account_mode": "paper", "capped": True}
    with patch("vinu_portfolio.server.app.PortfolioService.compute_daily_allocation", new=AsyncMock(return_value={"status": "empty", "weights": []})), \
         patch("vinu_portfolio.capital_plan.fetch_capital_ledger", new=AsyncMock(return_value=ledger)):
        body = TestClient(create_app()).get("/portfolio/capital-plan").json()
    assert body["capital_plan"]["status"] == "no_allocation" and body["capital_plan"]["ledger"]["free_cash"] == 12.0
