"""Around-the-clock orders: the guard judges the session from the broker's clock, enforces limit-only outside regular hours,
the overnight attribute and the mandate's allowed sessions; the broker marks extended-hours orders."""
from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from vinu_agent.broker.alpaca import AlpacaBroker
from vinu_agent.broker.daily_limits import DailyLimitStore
from vinu_agent.broker.guard_codes import ReasonCode
from vinu_agent.broker.mandate import TradingMandate
from vinu_agent.broker.order_guard import OrderGuard
from vinu_infra.sessions import NY, TRADABLE_SESSIONS


def _at(d, h, m=0):                      # October 2026: Monday the 5th
    return datetime(2026, 10, d, h, m, tzinfo=NY).isoformat()


def _guard(when: str, *, is_open=False, attrs=("overnight_tradable",), **mandate_kw) -> OrderGuard:
    broker = MagicMock()
    broker.get_clock.return_value = {"is_open": is_open, "timestamp": when, "next_open": "tomorrow"}
    broker.get_asset.return_value = {"attributes": list(attrs)}
    broker.get_account.return_value = MagicMock(equity=100_000.0, cash=100_000.0, portfolio_value=100_000.0, buying_power=100_000.0)
    mandate = TradingMandate(max_position_pct=1.0, require_active_artifact=False, **mandate_kw)
    return OrderGuard(mandate=mandate, broker=broker, daily_limit_store=DailyLimitStore(":memory:"),
                      portfolio_api_url="http://127.0.0.1:9")


@pytest.fixture(autouse=True)
def isolated_stores():
    from vinu_agent.broker.symbol_limits import SymbolLimitStore, reset_limit_store
    from vinu_agent.broker.symbol_overrides import SymbolOverrideStore, reset_override_store

    reset_override_store(SymbolOverrideStore(":memory:"))
    reset_limit_store(SymbolLimitStore(":memory:"))
    yield
    reset_override_store(None)
    reset_limit_store(None)


def check(g, order_type):
    return g.check("SPY", "buy", qty=1, price=100.0, order_type=order_type)


def test_regular_session_allows_market_orders():
    assert check(_guard(_at(5, 11), is_open=True), "market")


@pytest.mark.parametrize("hour", [5, 17, 22])          # premarket, afterhours, overnight
def test_outside_regular_hours_a_market_order_is_refused_with_a_way_forward_and_a_limit_order_passes(hour):
    g = _guard(_at(5, hour))
    refused = check(g, "market")
    assert not refused and refused.code == ReasonCode.LIMIT_ONLY_OUTSIDE_REGULAR and "limit order" in refused.reason
    assert check(g, "limit")


def test_overnight_needs_the_overnight_tradable_attribute_and_fails_closed():
    assert not check(_guard(_at(5, 22), attrs=("fractionable",)), "limit").code != ReasonCode.NOT_OVERNIGHT_TRADABLE
    g = _guard(_at(5, 22))
    g._broker.get_asset.side_effect = OSError("down")
    refused = check(g, "limit")
    assert not refused and refused.code == ReasonCode.NOT_OVERNIGHT_TRADABLE


def test_premarket_does_not_need_the_overnight_attribute():
    assert check(_guard(_at(5, 5), attrs=()), "limit")


def test_the_mandate_can_exclude_a_session():
    g = _guard(_at(5, 22), allowed_sessions=("regular", "premarket"))
    refused = check(g, "limit")
    assert not refused and refused.code == ReasonCode.SESSION_NOT_ALLOWED


def test_the_weekend_gap_queues_unless_the_mandate_requires_an_open_market():
    saturday = _at(10, 12)
    assert check(_guard(saturday, require_market_open=False), "market")
    refused = check(_guard(saturday, require_market_open=True), "market")
    assert not refused and refused.code == ReasonCode.MARKET_CLOSED


def test_a_regular_session_holiday_is_caught_by_the_broker_clock_when_an_open_market_is_required():
    refused = check(_guard(_at(5, 11), is_open=False, require_market_open=True), "market")
    assert not refused and refused.code == ReasonCode.MARKET_CLOSED
    assert check(_guard(_at(5, 11), is_open=False, require_market_open=False), "market")


def test_a_replay_broker_is_judged_by_its_own_clock_and_skips_the_overnight_attribute_lookup():
    g = _guard(_at(5, 22))
    g._broker.get_clock.return_value = {"timestamp": datetime(2026, 10, 5, 22, tzinfo=NY).astimezone().isoformat(), "replay": True}
    g._broker.get_asset.side_effect = AttributeError("replay broker has no assets")
    assert check(g, "limit")


def test_the_default_mandate_allows_every_session_and_loads_from_yaml(tmp_path):
    assert TradingMandate().allowed_sessions == TRADABLE_SESSIONS
    p = tmp_path / "m.yaml"
    p.write_text("allowed_sessions: [regular, overnight]\n", encoding="utf-8")
    assert TradingMandate.load(p).allowed_sessions == ("regular", "overnight")
    p.write_text("allowed_sessions: all\n", encoding="utf-8")
    assert TradingMandate.load(p).allowed_sessions == TRADABLE_SESSIONS
    assert TradingMandate.load(p).to_dict()["allowed_sessions"] == list(TRADABLE_SESSIONS)


# ---- the broker marks extended-hours orders ----------------------------------------------------------------------------

def _broker(monkeypatch, now: str):
    sent = {}
    b = AlpacaBroker.__new__(AlpacaBroker)
    b._post = lambda path, payload: sent.update(payload) or {"id": "x"}
    monkeypatch.setattr("time.time", lambda: datetime.fromisoformat(now).timestamp())
    return b, sent


def test_an_overnight_limit_order_is_sent_as_a_day_extended_hours_order(monkeypatch):
    b, sent = _broker(monkeypatch, _at(5, 22))
    b.submit_order("SPY", 1, "buy", order_type="limit", limit_price=780.0, time_in_force="gtc", client_order_id="c1")
    assert sent["extended_hours"] is True and sent["time_in_force"] == "day" and sent["type"] == "limit"


def test_a_regular_session_order_is_unchanged(monkeypatch):
    b, sent = _broker(monkeypatch, _at(5, 11))
    b.submit_order("SPY", 1, "buy", order_type="market")
    assert "extended_hours" not in sent and sent["type"] == "market"


@pytest.mark.parametrize("kw", [dict(order_type="market"), dict(order_type="limit"),
                                dict(order_type="limit", limit_price=780.0, take_profit_price=800.0)])
def test_outside_regular_hours_the_broker_call_refuses_what_alpaca_would_refuse(monkeypatch, kw):
    b, sent = _broker(monkeypatch, _at(5, 22))
    with pytest.raises(ValueError):
        b.submit_order("SPY", 1, "buy", **kw)
    assert sent == {}


# ---- a strategy trades only the sessions it was approved for, and smaller where the test said to ------------------------

def _active_artifact(store, *, sessions, hints=None):
    import json

    from vinu_research.models import Artifact, ArtifactStatus

    a = Artifact.create("strategy", "SPY-x", universe=["SPY"])
    a.status = ArtifactStatus.ACTIVE
    a.bar_interval, a.trading_sessions = "1h", sessions
    a.bar_evidence = json.dumps({"verified": True, "chosen_session": "all",
                                 "bars": [{"interval": "1h", "session": "all", "session_hints": hints or {}}]})
    store.upsert_artifact(a)
    return a


@pytest.fixture
def strategy_store(tmp_path):
    from vinu_research.storage.strategy_store import SqliteStrategyStore

    s = SqliteStrategyStore(tmp_path / "s.db")
    yield s
    s.close()


def _guard_with_artifacts(when, store):
    g = _guard(when)
    g._mandate.require_active_artifact = True
    return g


def test_an_overnight_order_is_refused_for_a_strategy_approved_for_regular_hours_only(strategy_store):
    from unittest.mock import patch

    _active_artifact(strategy_store, sessions="regular")
    with patch("vinu_agent.broker.research_link.get_strategy_store", return_value=strategy_store):
        g = _guard_with_artifacts(_at(5, 22), strategy_store)
        refused = check(g, "limit")
        assert not refused and refused.code == ReasonCode.SESSION_NOT_ALLOWED and "regular" in refused.reason


def test_the_session_a_strategy_is_approved_for_passes_and_is_sized_by_its_hint(strategy_store):
    from unittest.mock import patch

    hints = {"overnight": {"verdict": "reduce", "size_multiplier": 0.5}}
    _active_artifact(strategy_store, sessions="regular,overnight", hints=hints)
    with patch("vinu_agent.broker.research_link.get_strategy_store", return_value=strategy_store):
        g = _guard_with_artifacts(_at(5, 22), strategy_store)
        assert check(g, "limit")
        m = g.position_size_multiplier("SPY", "buy", qty=10, price=100.0)
        assert m.multiplier == 0.5 and m.binding == "session"
        regular = _guard_with_artifacts(_at(5, 11), strategy_store)
        regular._broker.get_clock.return_value["is_open"] = True
        assert check(regular, "market") and regular.position_size_multiplier("SPY", "buy", qty=10, price=100.0).multiplier == 1.0


def test_an_artifact_that_was_never_measured_per_session_is_not_restricted(strategy_store):
    from unittest.mock import patch

    _active_artifact(strategy_store, sessions="")
    with patch("vinu_agent.broker.research_link.get_strategy_store", return_value=strategy_store):
        assert check(_guard_with_artifacts(_at(5, 22), strategy_store), "limit")
