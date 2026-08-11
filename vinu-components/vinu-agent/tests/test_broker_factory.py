"""Tests for the broker abstraction -- `broker/base.py`'s `Broker`
Protocol and `broker/factory.py`'s `get_live_broker()`. Follow-up to
`component-consolidation-plan.md`: makes "which broker provider" one real
decision point instead of `AlpacaBroker()` hardcoded at 6 call sites,
Alpaca staying the default so every existing deployment is unaffected.
"""

from __future__ import annotations

import pytest

from vinu_agent.broker.alpaca import AlpacaBroker
from vinu_agent.broker.base import Broker
from vinu_agent.broker.factory import DEFAULT_PROVIDER, get_live_broker


class TestGetLiveBroker:
    def test_default_provider_is_alpaca(self, monkeypatch) -> None:
        monkeypatch.delenv("VINU_AGENT_BROKER_PROVIDER", raising=False)
        broker = get_live_broker()
        assert isinstance(broker, AlpacaBroker)

    def test_explicit_alpaca_provider(self) -> None:
        broker = get_live_broker("alpaca")
        assert isinstance(broker, AlpacaBroker)

    def test_env_var_selects_provider(self, monkeypatch) -> None:
        monkeypatch.setenv("VINU_AGENT_BROKER_PROVIDER", "alpaca")
        broker = get_live_broker()
        assert isinstance(broker, AlpacaBroker)

    def test_provider_name_is_case_insensitive(self) -> None:
        broker = get_live_broker("ALPACA")
        assert isinstance(broker, AlpacaBroker)

    def test_unknown_provider_raises_a_clear_error(self) -> None:
        with pytest.raises(ValueError, match="Unknown broker provider 'ibkr'"):
            get_live_broker("ibkr")

    def test_default_provider_constant_matches_actual_default(self, monkeypatch) -> None:
        assert DEFAULT_PROVIDER == "alpaca"


class TestBrokerProtocol:
    def test_alpaca_broker_satisfies_the_protocol(self) -> None:
        assert isinstance(AlpacaBroker(), Broker)

    def test_historical_fill_broker_satisfies_the_protocol(self) -> None:
        from vinu_agent.broker.historical_broker import HistoricalFillBroker

        broker = HistoricalFillBroker(as_of="2026-01-01T00:00:00Z")
        assert isinstance(broker, Broker)
