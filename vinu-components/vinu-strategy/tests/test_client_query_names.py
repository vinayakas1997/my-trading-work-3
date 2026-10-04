"""Contract: vinu-strategy's clients send the query names the routes declare. The analysis routes take `from_ts` / `to_ts`
(not `from` / `to`); `/features/{symbol}` has no window at all, so its client must not pretend to send one. (2026-10-04 scan.)"""

from __future__ import annotations

from vinu_strategy.clients.correlation_client import CorrelationClient
from vinu_strategy.clients.features_client import FeaturesClient


def _spy(client):
    calls = []
    client._get = lambda path, params=None, **kw: calls.append((path, params)) or {}
    return calls


def _make(cls):
    c = cls.__new__(cls)
    return c


def test_correlation_client_sends_from_ts_and_to_ts():
    c = _make(CorrelationClient)
    calls = _spy(c)
    c.get_impact("AAPL", 1, 2)
    c.get_correlation("AAPL", 1, 2)
    c.get_drawdown("AAPL", 1, 2)
    assert calls == [("/analysis/impact/AAPL", {"from_ts": "1", "to_ts": "2"}),
                     ("/analysis/correlation/AAPL", {"from_ts": "1", "to_ts": "2"}),
                     ("/analysis/drawdown/AAPL", {"from_ts": "1", "to_ts": "2"})]


def test_features_client_sends_indicators_and_as_of_and_no_window():
    c = _make(FeaturesClient)
    calls = _spy(c)
    c.get_features("AAPL", ["sma_20", "rsi_14"], as_of=5)
    assert calls == [("/features/AAPL", {"indicators": "sma_20,rsi_14", "as_of": "5"})]
    import inspect
    assert "from_ts" not in inspect.signature(FeaturesClient.get_features).parameters
