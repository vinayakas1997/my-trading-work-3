"""Per-session attribution of a strategy's returns, the risk hints that follow, and validation under regular and all sessions."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest

from vinu_infra.sessions import NY
from vinu_research.bar_validation import validate_across_bars
from vinu_research.config import ResearchConfig
from vinu_research.models import Artifact
from vinu_research.promotion import meets_promotion_bar
from vinu_research.session_stats import approved_sessions, risk_hints, session_breakdown


def _series(n_days=120, *, regular=0.0004, overnight=0.0002, premarket=0.0, afterhours=0.0, vol=0.002, over_vol=0.004, seed=5):
    """15-minute returns for n weekdays with a different mean / volatility per session (index = naive UTC bar-open times)."""
    rng = np.random.default_rng(seed)
    stamps, vals = [], []
    for d in pd.bdate_range("2026-03-02", periods=n_days):
        for minute in range(0, 24 * 60, 15):
            t = datetime(d.year, d.month, d.day, minute // 60, minute % 60, tzinfo=NY)
            h = minute / 60
            if 9.5 <= h < 16:
                mean, sd = regular, vol
            elif 20 <= h or h < 4:
                mean, sd = overnight, over_vol
            elif 4 <= h < 9.5:
                mean, sd = premarket, over_vol
            else:
                mean, sd = afterhours, over_vol
            stamps.append(t.astimezone(timezone.utc).replace(tzinfo=None))
            vals.append(rng.normal(mean, sd))
    return pd.Series(vals, index=pd.DatetimeIndex(stamps))


def test_each_return_is_attributed_to_the_session_its_bar_opened_in():
    b = session_breakdown(_series(), periods_per_year=96 * 252.0)
    assert set(b) == {"premarket", "regular", "afterhours", "overnight"}
    # 120 weekdays = 24 Fridays; a Friday evening is not tradable (the week's overnight session ends Friday 04:00)
    assert b["regular"]["bars"] == 120 * 26 and b["overnight"]["bars"] == 120 * 32 - 24 * 16
    assert b["regular"]["total_return"] > 0 and b["overnight"]["total_return"] > 0
    # the rest of the return is in `closed` (the Friday-evening bars of this synthetic series): never attributed to a session
    assert 0.9 < sum(v["share_of_return"] for v in b.values()) < 1.0


def test_hints_trade_the_good_sessions_reduce_the_volatile_one_avoid_the_losing_one_and_skip_the_unmeasured():
    b = session_breakdown(_series(overnight=0.0003, premarket=-0.0006), periods_per_year=96 * 252.0)
    h = risk_hints(b)
    assert h["regular"]["verdict"] == "trade" and h["regular"]["size_multiplier"] == 1.0
    assert h["overnight"]["verdict"] == "reduce" and 0.25 <= h["overnight"]["size_multiplier"] < 1.0   # 2x the volatility
    assert h["premarket"]["verdict"] == "avoid" and h["premarket"]["size_multiplier"] == 0.0
    assert approved_sessions(h) == ["regular", "overnight"] or approved_sessions(h) == ["regular", "afterhours", "overnight"]


def test_a_session_with_too_few_bars_is_not_approved_no_evidence_no_trading():
    short = _series(n_days=3)
    h = risk_hints(session_breakdown(short))
    assert all(v["verdict"] == "insufficient_data" and v["size_multiplier"] == 0.0 for v in h.values())
    assert approved_sessions(h) == []


def test_the_multiplier_never_goes_below_the_floor():
    h = risk_hints(session_breakdown(_series(over_vol=0.05, overnight=0.01), periods_per_year=96 * 252.0))
    assert h["overnight"]["size_multiplier"] == 0.25


def test_an_empty_return_series_gives_no_breakdown():
    assert session_breakdown(pd.Series([], dtype=float)) == {}


# ---- validation runs every bar size under regular hours and under all 24 hours ----------------------------------------

def _run(sharpe=0.9, trades=60, hints=None):
    return {"id": 1, "symbol": "AMD", "total_iterations": 1, "outcome_status": "passed", "best_sharpe": sharpe,
            "deflated_sharpe": 1.2, "holdout_passed": True, "stress_test_passed": True, "pbo": None, "diagnosis": "",
            "attempt": {"sharpe": sharpe, "max_drawdown": -0.1, "total_return": 0.2, "trade_count": trades, "win_rate": 0.4},
            "session_hints": hints, "session_breakdown": {}}


class _Svc:
    def __init__(self, answers):
        self.config = ResearchConfig()
        self.answers, self.calls = answers, []

    async def run_research(self, **kw):
        self.calls.append(kw)
        return self.answers[(kw["interval"], kw.get("session", "regular"))]


def _validate(answers, sessions=None):
    svc = _Svc(answers)
    healthy = lambda *_a: {"backfill_status": "complete", "first_bar_ts": 1, "last_bar_ts": 10**12}
    out = asyncio.run(validate_across_bars(svc, symbol="AMD", strategy_code="class UserStrategy:\n    pass\n",
                                           to_date="2026-10-01", catalog_lookup=healthy, bars=["1d"], sessions=sessions))
    return svc, out


def test_each_bar_size_is_tested_under_regular_hours_and_under_all_sessions():
    hints = {"regular": {"verdict": "trade", "size_multiplier": 1.0}, "overnight": {"verdict": "reduce", "size_multiplier": 0.5}}
    svc, out = _validate({("1d", "regular"): _run(sharpe=0.9), ("1d", "all"): _run(sharpe=1.4, hints=hints)})
    assert [c.get("session", "regular") for c in svc.calls] == ["regular", "all"]
    assert out["chosen_session"] == "all" and out["chosen"]["session_hints"] == hints
    assert out["passing"] == ["1d/regular", "1d/all"] and out["passing_bars"] == ["1d"]


def test_the_default_session_sets_come_from_the_environment(monkeypatch):
    monkeypatch.setenv("VINU_VALIDATION_SESSIONS", "regular")
    svc, _ = _validate({("1d", "regular"): _run()})
    assert len(svc.calls) == 1


# ---- the artifact and the promotion bar keep the sessions it was approved for ----------------------------------------

def test_the_promotion_bar_reads_the_row_of_the_chosen_session():
    import json

    a = Artifact.create("strategy", "AMD-x", universe=["AMD"])
    a.deflated_sharpe, a.holdout_passed, a.stress_test_passed, a.pbo = 1.2, True, True, None
    a.bar_interval = "1d"
    rows = [{"interval": "1d", "session": "regular", "pbo_waived": True, "trade_count": 5},
            {"interval": "1d", "session": "all", "pbo_waived": True, "trade_count": 80}]
    a.bar_evidence = json.dumps({"verified": True, "chosen_session": "all", "bars": rows})
    assert meets_promotion_bar(a, ResearchConfig()).eligible                 # judged on the "all" row (80 trades)
    a.bar_evidence = json.dumps({"verified": True, "chosen_session": "regular", "bars": rows})
    assert not meets_promotion_bar(a, ResearchConfig()).eligible             # the regular row has only 5 trades


# ---- the equity curve reaches the attribution WITH its dates ------------------------------------------------------------
# Seen on the real AMD run: fetch_equity_returns gave the returns a row-number index, the attribution read 0, 1, 2 ... as
# nanoseconds after 1970 (19:00 New York on 31 December 1969) and put every bar of a year in "afterhours".

def _tools_with_equity(rows):
    from vinu_research.tools import ResearchTools

    class _Sim:
        async def get(self, path, **kw):
            assert path.endswith("/equity")
            return rows

    tools = ResearchTools(ResearchConfig())
    tools._simulator_client = _Sim()
    return tools


def _equity_rows():
    # hourly bars, 2026-10-06 (EDT = UTC-4): 14:00-21:00 UTC is 10:00-17:00 New York
    return [{"date": f"2026-10-06 {h:02d}:00:00", "portfolio_value": 1_000_000.0 * 1.01 ** i} for i, h in enumerate(range(14, 22))]


def test_the_session_breakdown_of_a_real_shaped_equity_curve_lands_each_bar_in_its_own_session():
    tools = _tools_with_equity(_equity_rows())
    returns = asyncio.run(tools.fetch_equity_returns("run-1", keep_dates=True))
    assert isinstance(returns.index, pd.DatetimeIndex)
    b = session_breakdown(returns, periods_per_year=96 * 252.0)
    # the first bar has no return; the rest open at 11:00 ... 17:00 New York
    assert (b["regular"]["bars"], b["afterhours"]["bars"], b["premarket"]["bars"], b["overnight"]["bars"]) == (5, 2, 0, 0)


def test_the_default_still_returns_the_row_number_index_the_older_callers_align_on():
    returns = asyncio.run(_tools_with_equity(_equity_rows()).fetch_equity_returns("run-1"))
    assert not isinstance(returns.index, pd.DatetimeIndex) and len(returns) == 7
